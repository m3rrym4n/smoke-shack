from __future__ import annotations

import asyncio
import json
import logging
import urllib.request
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, cast
from urllib.parse import urlsplit, urlunsplit

import websockets

from app.config import EntityConfig
from app.service import CookService, GrillSnapshot

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@dataclass
class HAStatus:
    configured: bool
    connected: bool = False
    last_error: str | None = None
    last_event_at: datetime | None = None
    grill_name: str | None = None
    grill_title: str | None = None
    grill_maker: str | None = None


class HAClient(Protocol):
    status: HAStatus

    def snapshots(self) -> AsyncIterator[GrillSnapshot]: ...


async def ingest(
    client: HAClient,
    service: CookService,
    sample_interval_seconds: int,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    latest_snapshot: GrillSnapshot | None = None

    async def sample_on_tick() -> None:
        logger.info("HA sample tick started: interval=%ss", sample_interval_seconds)
        while True:
            await sleep(sample_interval_seconds)
            logger.debug(
                "HA sample tick: connected=%s snapshot=%s",
                client.status.connected,
                latest_snapshot is not None,
            )
            if client.status.connected and latest_snapshot is not None:
                service.process(latest_snapshot)

    tick_task = asyncio.create_task(sample_on_tick())
    try:
        async for snapshot in client.snapshots():
            latest_snapshot = snapshot
            if snapshot.grill_name:
                client.status.grill_name = snapshot.grill_name
            service.process(snapshot)
    finally:
        tick_task.cancel()
        await asyncio.gather(tick_task, return_exceptions=True)


class HomeAssistantClient:
    def __init__(
        self,
        url: str,
        token: str,
        entities: EntityConfig,
        poll_interval_seconds: int = 10,
        max_size_bytes: int = 67_108_864,
        coalesce_window_seconds: float = 1.0,
    ) -> None:
        parsed = urlsplit(url)
        scheme = {"http": "ws", "https": "wss"}.get(parsed.scheme, parsed.scheme)
        self.websocket_url = urlunsplit((scheme, parsed.netloc, "/api/websocket", "", ""))
        self.template_url = urlunsplit((parsed.scheme, parsed.netloc, "/api/template", "", ""))
        self.host = parsed.hostname or parsed.netloc
        self.token = token
        self.entities = entities
        self.entity_ids = entities.all
        self.poll_interval_seconds = poll_interval_seconds
        self.max_size_bytes = max_size_bytes
        self.coalesce_window_seconds = coalesce_window_seconds
        self.status = HAStatus(configured=bool(url and token))

    async def snapshots(self) -> AsyncIterator[GrillSnapshot]:
        delay = 1
        while True:
            try:
                async for snapshot in self._connected():
                    delay = 1
                    yield snapshot
            except (OSError, websockets.WebSocketException, RuntimeError) as exc:
                self.status.connected = False
                self.status.last_error = self._short_reason(exc)
                logger.warning("HA connection failed: %s", self.status.last_error)
                logger.info("HA websocket disconnected; retrying in %ss", delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)

    async def _connected(self) -> AsyncIterator[GrillSnapshot]:
        async with websockets.connect(self.websocket_url, max_size=self.max_size_bytes) as socket:
            await socket.recv()
            await socket.send(json.dumps({"type": "auth", "access_token": self.token}))
            auth = json.loads(await socket.recv())
            if auth.get("type") != "auth_ok":
                raise RuntimeError("Home Assistant authentication failed")
            self.status.connected = True
            self.status.last_error = None
            logger.info("HA websocket connected to %s", self.host)
            await self._refresh_device_info()
            await socket.send(json.dumps({"id": 1, "type": "get_states"}))
            initial = json.loads(await socket.recv())
            self.status.last_event_at = datetime.now(UTC).replace(microsecond=0)
            states = self._configured_states(initial.get("result", []))
            del initial
            yield self._snapshot(states)
            await socket.send(
                json.dumps({"id": 2, "type": "subscribe_events", "event_type": "state_changed"})
            )
            request_id = 3
            while True:
                try:
                    raw = await asyncio.wait_for(socket.recv(), self.poll_interval_seconds)
                except TimeoutError:
                    await socket.send(json.dumps({"id": request_id, "type": "get_states"}))
                    request_id += 1
                    raw = await socket.recv()
                message = json.loads(raw)
                del raw
                self.status.last_event_at = datetime.now(UTC).replace(microsecond=0)
                if message.get("type") == "result" and isinstance(message.get("result"), list):
                    states = self._configured_states(message["result"])
                    del message
                    yield self._snapshot(states)
                    continue
                event = message.get("event", {}).get("data", {})
                entity_id = event.get("entity_id")
                if entity_id not in self.entity_ids:
                    continue
                if event.get("new_state") is not None:
                    states[entity_id] = event["new_state"]
                    await self._coalesce_events(socket, states)
                    yield self._snapshot(states)

    async def _coalesce_events(self, socket: Any, states: dict[str, dict[str, Any]]) -> None:
        deadline = asyncio.get_running_loop().time() + self.coalesce_window_seconds
        while (remaining := deadline - asyncio.get_running_loop().time()) > 0:
            try:
                raw = await asyncio.wait_for(socket.recv(), remaining)
            except TimeoutError:
                return
            message = json.loads(raw)
            if message.get("type") == "result" and isinstance(message.get("result"), list):
                states.clear()
                states.update(self._configured_states(message["result"]))
                continue
            event = message.get("event", {}).get("data", {})
            entity_id = event.get("entity_id")
            if entity_id in self.entity_ids and event.get("new_state") is not None:
                states[entity_id] = event["new_state"]

    async def _refresh_device_info(self) -> None:
        entity_id = self.entities.pit_climate
        template = (
            "{{ device_attr(device_id('"
            + entity_id
            + "'), 'model') }}|{{ device_attr(device_id('"
            + entity_id
            + "'), 'manufacturer') }}|{{ device_attr(device_id('"
            + entity_id
            + "'), 'name_by_user') }}"
        )
        request = urllib.request.Request(
            self.template_url,
            data=json.dumps({"template": template}).encode(),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            output = await asyncio.to_thread(self._read_template, request)
            model, manufacturer, name_by_user = parse_device_template(output)
        except (OSError, RuntimeError, ValueError):
            logger.warning("HA device information lookup failed for %s", self.host)
            return
        self.status.grill_title = name_by_user or model
        self.status.grill_maker = manufacturer

    @staticmethod
    def _read_template(request: urllib.request.Request) -> str:
        with urllib.request.urlopen(request, timeout=10) as response:
            return cast(bytes, response.read()).decode("utf-8")

    def _configured_states(self, result: object) -> dict[str, dict[str, Any]]:
        if not isinstance(result, list):
            return {}
        return {
            item["entity_id"]: item
            for item in result
            if isinstance(item, dict) and item.get("entity_id") in self.entity_ids
        }

    def _short_reason(self, exc: BaseException) -> str:
        reason = str(exc).splitlines()[0]
        if self.token:
            reason = reason.replace(self.token, "<redacted>")
        reason = reason.replace(self.websocket_url, self.host)
        return (reason or type(exc).__name__)[:160]

    def _snapshot(self, states: dict[str, dict[str, Any]]) -> GrillSnapshot:
        def state(entity_id: str) -> str | None:
            item = states.get(entity_id)
            return cast(str | None, item.get("state") if item else None)

        def number(entity_id: str) -> float | None:
            value = state(entity_id)
            if value is None or value in {"unknown", "unavailable"}:
                return None
            try:
                return float(value)
            except ValueError:
                return None

        def attribute_number(entity_id: str, attribute: str) -> float | None:
            value = states.get(entity_id, {}).get("attributes", {}).get(attribute)
            try:
                return float(value) if value is not None else None
            except (TypeError, ValueError):
                return None

        def connected(entity_id: str) -> bool:
            return (state(entity_id) or "").casefold() == "on"

        climate = states.get(self.entities.pit_climate, {})
        mode = climate.get("state")
        friendly_name = climate.get("attributes", {}).get("friendly_name")
        return GrillSnapshot(
            grill_name=(friendly_name.strip() if isinstance(friendly_name, str) else None) or None,
            pit_temp=number(self.entities.pit_temp),
            setpoint=attribute_number(self.entities.pit_climate, "temperature"),
            probe1=number(self.entities.probe1_temp),
            probe2=number(self.entities.probe2_temp),
            probe1_connected=connected(self.entities.probe1_connection),
            probe2_connected=connected(self.entities.probe2_connection),
            probe1_target=attribute_number(self.entities.probe1_climate, "temperature"),
            probe2_target=attribute_number(self.entities.probe2_climate, "temperature"),
            fire_state=state(self.entities.fire_state),
            power_state=state(self.entities.power_state),
            warning=state(self.entities.warning),
            hvac_mode=cast(str | None, mode),
            extra_probes={entity: number(entity) for entity in self.entities.extra_probes},
        )


def parse_device_template(output: str) -> tuple[str | None, str | None, str | None]:
    parts = output.strip().split("|")
    if len(parts) != 3:
        raise ValueError("Unexpected Home Assistant device template output")

    def value(part: str) -> str | None:
        cleaned = part.strip()
        return cleaned if cleaned and cleaned != "None" else None

    return value(parts[0]), value(parts[1]), value(parts[2])
