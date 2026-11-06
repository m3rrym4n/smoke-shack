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
from sqlalchemy.orm import Session, sessionmaker

from app.config import EntityConfig
from app.equipment import ConnectedEquipment, WatchedChannel, connected_equipment
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


@dataclass(frozen=True)
class HARegistrySnapshot:
    devices: tuple[dict[str, Any], ...]
    entities: tuple[dict[str, Any], ...]
    states: tuple[dict[str, Any], ...]


class HAClient(Protocol):
    status: HAStatus

    def snapshots(self) -> AsyncIterator[GrillSnapshot]: ...

    async def registry_snapshot(self) -> HARegistrySnapshot: ...


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
                snapshot_on_tick = getattr(client, "snapshot_on_tick", None)
                service.process(
                    snapshot_on_tick(latest_snapshot)
                    if callable(snapshot_on_tick)
                    else latest_snapshot
                )

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
        *,
        template_url: str | None = None,
        host: str | None = None,
        sessions: sessionmaker[Session] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if template_url is None:
            parsed = urlsplit(url)
            scheme = {"http": "ws", "https": "wss"}.get(parsed.scheme, parsed.scheme)
            self.websocket_url = urlunsplit((scheme, parsed.netloc, "/api/websocket", "", ""))
            self.template_url = urlunsplit(
                (parsed.scheme, parsed.netloc, "/api/template", "", "")
            )
            self.host = parsed.hostname or parsed.netloc
        else:
            self.websocket_url = url
            self.template_url = template_url
            self.host = host or urlsplit(url).hostname or urlsplit(url).netloc
        self.token = token
        self.entities = entities
        self.sessions = sessions
        self._equipment: ConnectedEquipment | None = self._legacy_equipment()
        self._watch_list_dirty = False
        self.entity_ids = self._watch_entity_ids(self._equipment, legacy=True)
        self.poll_interval_seconds = poll_interval_seconds
        self.max_size_bytes = max_size_bytes
        self.coalesce_window_seconds = coalesce_window_seconds
        self.clock = clock or (lambda: datetime.now(UTC).replace(microsecond=0))
        self.status = HAStatus(configured=bool(url and token))
        self._last_states: dict[str, dict[str, Any]] = {}
        self._stale: bool | None = None
        self._invalid_last_reported_warned = False

    def _legacy_equipment(self) -> ConnectedEquipment:
        channels = [
            WatchedChannel("pit", self.entities.pit_temp, self.entities.pit_climate),
            WatchedChannel("probe1", self.entities.probe1_temp, self.entities.probe1_climate),
            WatchedChannel("probe2", self.entities.probe2_temp, self.entities.probe2_climate),
        ]
        channels.extend(
            WatchedChannel(entity.rsplit(".", 1)[-1], entity, None)
            for entity in self.entities.extra_probes
        )
        return ConnectedEquipment(0, tuple(channels))

    def _is_legacy(self, equipment: ConnectedEquipment | None) -> bool:
        return equipment is not None and any(
            channel.key == "pit" and channel.source_entity == self.entities.pit_temp
            for channel in equipment.channels
        )

    def _watch_entity_ids(
        self, equipment: ConnectedEquipment | None, *, legacy: bool
    ) -> set[str]:
        if equipment is None:
            return set()
        ids = {
            entity
            for channel in equipment.channels
            for entity in (channel.source_entity, channel.target_entity)
            if entity
        }
        if legacy:
            ids.update(self.entities.all)
        ids.update(equipment.status_entities.values())
        return ids

    def refresh_watch_list(self) -> bool:
        """Reload connected channels; return whether the watched equipment changed."""
        if self.sessions is None:
            return False
        with self.sessions() as session:
            equipment = connected_equipment(session)
        changed = equipment != self._equipment
        self._equipment = equipment
        self.entity_ids = self._watch_entity_ids(equipment, legacy=self._is_legacy(equipment))
        self._watch_list_dirty = self._watch_list_dirty or changed
        return changed

    async def registry_snapshot(self) -> HARegistrySnapshot:
        """Read the HA registries and current states without changing HA."""
        try:
            async with websockets.connect(
                self.websocket_url, max_size=self.max_size_bytes
            ) as socket:
                await socket.recv()
                await socket.send(json.dumps({"type": "auth", "access_token": self.token}))
                auth = json.loads(await socket.recv())
                if auth.get("type") != "auth_ok":
                    raise RuntimeError("Home Assistant authentication failed")
                devices = await self._registry_request(
                    socket, 1, "config/device_registry/list"
                )
                entities = await self._registry_request(
                    socket, 2, "config/entity_registry/list"
                )
                states = await self._registry_request(socket, 3, "get_states")
                return HARegistrySnapshot(
                    devices=tuple(item for item in devices if isinstance(item, dict)),
                    entities=tuple(item for item in entities if isinstance(item, dict)),
                    states=tuple(item for item in states if isinstance(item, dict)),
                )
        except (OSError, websockets.WebSocketException, RuntimeError) as exc:
            self.status.last_error = self._short_reason(exc)
            raise RuntimeError(self.status.last_error) from exc

    @staticmethod
    async def _registry_request(socket: Any, request_id: int, kind: str) -> list[Any]:
        await socket.send(json.dumps({"id": request_id, "type": kind}))
        response = json.loads(await socket.recv())
        if response.get("type") != "result" or not response.get("success"):
            message = response.get("error", {}).get("message", f"{kind} failed")
            raise RuntimeError(str(message))
        result = response.get("result")
        if not isinstance(result, list):
            raise RuntimeError(f"Unexpected {kind} response")
        return result

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
            self._stale = None
            self._invalid_last_reported_warned = False
            logger.info("HA websocket connected to %s", self.host)
            self.refresh_watch_list()
            if self._is_legacy(self._equipment):
                await self._refresh_device_info()
            await socket.send(json.dumps({"id": 1, "type": "get_states"}))
            initial = json.loads(await socket.recv())
            self.status.last_event_at = datetime.now(UTC).replace(microsecond=0)
            states = self._configured_states(initial.get("result", []))
            self._last_states = states
            self._watch_list_dirty = False
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
                self.refresh_watch_list()
                watch_changed = self._watch_list_dirty
                message = json.loads(raw)
                del raw
                self.status.last_event_at = datetime.now(UTC).replace(microsecond=0)
                if watch_changed:
                    await socket.send(json.dumps({"id": request_id, "type": "get_states"}))
                    request_id += 1
                    message = json.loads(await socket.recv())
                    self._watch_list_dirty = False
                if message.get("type") == "result" and isinstance(message.get("result"), list):
                    states = self._configured_states(message["result"])
                    self._last_states = states
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

    def snapshot_on_tick(self, latest_snapshot: GrillSnapshot) -> GrillSnapshot:
        """Rebuild time-sensitive snapshots from the latest known HA states."""
        if self._equipment is not None and self._equipment.stale_after_seconds is not None:
            return self._snapshot(self._last_states)
        return latest_snapshot

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

        equipment = self._equipment
        channels = {channel.key: channel for channel in equipment.channels} if equipment else {}
        legacy = self._is_legacy(equipment)

        def channel_value(key: str) -> float | None:
            channel = channels.get(key)
            return number(channel.source_entity) if channel else None

        def channel_target(key: str) -> float | None:
            channel = channels.get(key)
            if legacy:
                target_entity = {
                    "pit": self.entities.pit_climate,
                    "probe1": self.entities.probe1_climate,
                    "probe2": self.entities.probe2_climate,
                }.get(key)
            else:
                target_entity = channel.target_entity if channel is not None else None
            if target_entity is None:
                return None
            attribute = attribute_number(target_entity, "temperature")
            return attribute if attribute is not None else number(target_entity)

        climate = states.get(self.entities.pit_climate, {}) if legacy else {}
        mode = climate.get("state") if legacy else None
        friendly_name = climate.get("attributes", {}).get("friendly_name") if legacy else None
        status_entities = equipment.status_entities if equipment is not None else {}
        power = state(status_entities["power"]) if "power" in status_entities else None
        mapped_power = power.casefold() if power is not None else None
        lifecycle = not legacy and "power" in status_entities
        error = state(status_entities["error"]) if "error" in status_entities else None
        mapped_error = error.casefold() if error is not None else None

        stale = False
        last_reported_entity = status_entities.get("last_reported")
        stale_after = equipment.stale_after_seconds if equipment is not None else None
        if last_reported_entity is not None and stale_after is not None:
            last_reported = state(last_reported_entity)
            if last_reported is not None and last_reported.casefold() in {
                "unknown",
                "unavailable",
            }:
                stale = True
            elif last_reported is not None:
                try:
                    reported_at = datetime.fromisoformat(last_reported.replace("Z", "+00:00"))
                    if reported_at.tzinfo is None:
                        raise ValueError("timestamp has no timezone")
                    age = self.clock() - reported_at.astimezone(UTC)
                    stale = age.total_seconds() > stale_after
                except ValueError:
                    if not self._invalid_last_reported_warned:
                        logger.warning(
                            "HA last_reported for connected grill is not an ISO timestamp: %r",
                            last_reported,
                        )
                        self._invalid_last_reported_warned = True

            if (self._stale is None and stale) or (
                self._stale is not None and stale != self._stale
            ):
                logger.info("HA connected grill telemetry is %s", "stale" if stale else "fresh")
            self._stale = stale

        def mapped_binary(value: str | None, on: str, off: str) -> str | None:
            if value == "on":
                return on
            if value == "off":
                return off
            return None

        snapshot = GrillSnapshot(
            grill_name=(friendly_name.strip() if isinstance(friendly_name, str) else None) or None,
            pit_temp=channel_value("pit"),
            setpoint=channel_target("pit"),
            probe1=channel_value("probe1"),
            probe2=channel_value("probe2"),
            probe1_connected=(
                connected(self.entities.probe1_connection)
                if legacy
                else channel_value("probe1") is not None
            ),
            probe2_connected=(
                connected(self.entities.probe2_connection)
                if legacy
                else channel_value("probe2") is not None
            ),
            probe1_target=channel_target("probe1"),
            probe2_target=channel_target("probe2"),
            fire_state=(
                state(self.entities.fire_state)
                if legacy
                else mapped_binary(mapped_power, "Running", "Off")
            ),
            power_state=(
                state(self.entities.power_state)
                if legacy
                else mapped_binary(mapped_power, "On", "Off")
            ),
            warning=(
                state(self.entities.warning)
                if legacy
                else mapped_binary(mapped_error, "Problem", "None")
            ),
            hvac_mode=(
                cast(str | None, mode) if legacy else mapped_binary(mapped_power, "heat", "off")
            ),
            extra_probes=(
                {entity: number(entity) for entity in self.entities.extra_probes}
                if legacy
                else {
                    key: channel_value(key)
                    for key in channels
                    if key not in {"pit", "probe1", "probe2"}
                }
            ),
            extra_probe_targets=(
                {}
                if legacy
                else {
                    key: channel_target(key)
                    for key in channels
                    if key not in {"pit", "probe1", "probe2"}
                }
            ),
            cook_lifecycle_enabled=legacy or lifecycle,
            startup_ends_at_setpoint=lifecycle,
            max_setpoint=750 if lifecycle else 550,
            max_pit_temperature=750 if lifecycle else 600,
        )
        if not stale:
            return snapshot
        return GrillSnapshot(
            probe1_connected=None,
            probe2_connected=None,
            extra_probes={key: None for key in snapshot.extra_probes},
            extra_probe_targets={key: None for key in snapshot.extra_probe_targets},
            cook_lifecycle_enabled=snapshot.cook_lifecycle_enabled,
            startup_ends_at_setpoint=snapshot.startup_ends_at_setpoint,
            max_setpoint=snapshot.max_setpoint,
            max_pit_temperature=snapshot.max_pit_temperature,
            stale=True,
        )


def parse_device_template(output: str) -> tuple[str | None, str | None, str | None]:
    parts = output.strip().split("|")
    if len(parts) != 3:
        raise ValueError("Unexpected Home Assistant device template output")

    def value(part: str) -> str | None:
        cleaned = part.strip()
        return cleaned if cleaned and cleaned != "None" else None

    return value(parts[0]), value(parts[1]), value(parts[2])
