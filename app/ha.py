from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, cast
from urllib.parse import urlsplit, urlunsplit

import websockets

from app.config import EntityConfig
from app.service import GrillSnapshot

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@dataclass
class HAStatus:
    configured: bool
    connected: bool = False
    last_error: str | None = None
    last_event_at: datetime | None = None


class HAClient(Protocol):
    status: HAStatus

    def snapshots(self) -> AsyncIterator[GrillSnapshot]: ...


class HomeAssistantClient:
    def __init__(
        self, url: str, token: str, entities: EntityConfig, poll_interval_seconds: int = 10
    ) -> None:
        parsed = urlsplit(url)
        scheme = {"http": "ws", "https": "wss"}.get(parsed.scheme, parsed.scheme)
        self.websocket_url = urlunsplit((scheme, parsed.netloc, "/api/websocket", "", ""))
        self.host = parsed.hostname or parsed.netloc
        self.token = token
        self.entities = entities
        self.poll_interval_seconds = poll_interval_seconds
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
        async with websockets.connect(self.websocket_url) as socket:
            await socket.recv()
            await socket.send(json.dumps({"type": "auth", "access_token": self.token}))
            auth = json.loads(await socket.recv())
            if auth.get("type") != "auth_ok":
                raise RuntimeError("Home Assistant authentication failed")
            self.status.connected = True
            self.status.last_error = None
            logger.info("HA websocket connected to %s", self.host)
            await socket.send(json.dumps({"id": 1, "type": "get_states"}))
            initial = json.loads(await socket.recv())
            self.status.last_event_at = datetime.now(UTC).replace(microsecond=0)
            states = {item["entity_id"]: item for item in initial.get("result", [])}
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
                self.status.last_event_at = datetime.now(UTC).replace(microsecond=0)
                if message.get("type") == "result" and isinstance(message.get("result"), list):
                    states = {item["entity_id"]: item for item in message["result"]}
                    yield self._snapshot(states)
                    continue
                event = message.get("event", {}).get("data", {})
                entity_id = event.get("entity_id")
                if entity_id in self.entities.all and event.get("new_state") is not None:
                    states[entity_id] = event["new_state"]
                    yield self._snapshot(states)

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
        return GrillSnapshot(
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
