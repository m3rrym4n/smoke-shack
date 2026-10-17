from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any, Protocol, cast

import websockets

from app.config import EntityConfig
from app.service import GrillSnapshot


class HAClient(Protocol):
    def snapshots(self) -> AsyncIterator[GrillSnapshot]: ...


class HomeAssistantClient:
    def __init__(
        self, url: str, token: str, entities: EntityConfig, poll_interval_seconds: int = 10
    ) -> None:
        self.url = url.rstrip("/").replace("http://", "ws://").replace("https://", "wss://")
        self.token = token
        self.entities = entities
        self.poll_interval_seconds = poll_interval_seconds

    async def snapshots(self) -> AsyncIterator[GrillSnapshot]:
        delay = 1
        while True:
            try:
                async for snapshot in self._connected():
                    delay = 1
                    yield snapshot
            except (OSError, websockets.WebSocketException, RuntimeError):
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)

    async def _connected(self) -> AsyncIterator[GrillSnapshot]:
        async with websockets.connect(f"{self.url}/api/websocket") as socket:
            await socket.recv()
            await socket.send(json.dumps({"type": "auth", "access_token": self.token}))
            auth = json.loads(await socket.recv())
            if auth.get("type") != "auth_ok":
                raise RuntimeError("Home Assistant authentication failed")
            await socket.send(json.dumps({"id": 1, "type": "get_states"}))
            initial = json.loads(await socket.recv())
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
                if message.get("type") == "result" and isinstance(message.get("result"), list):
                    states = {item["entity_id"]: item for item in message["result"]}
                    yield self._snapshot(states)
                    continue
                event = message.get("event", {}).get("data", {})
                entity_id = event.get("entity_id")
                if entity_id in self.entities.all and event.get("new_state") is not None:
                    states[entity_id] = event["new_state"]
                    yield self._snapshot(states)

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

        climate = states.get(self.entities.pit_climate, {})
        mode = climate.get("state")
        return GrillSnapshot(
            pit_temp=number(self.entities.pit_temp),
            setpoint=number(self.entities.setpoint),
            probe1=number(self.entities.probe1_temp),
            probe2=number(self.entities.probe2_temp),
            fire_state=state(self.entities.fire_state),
            power_state=state(self.entities.power_state),
            hvac_mode=cast(str | None, mode),
            extra_probes={entity: number(entity) for entity in self.entities.extra_probes},
        )
