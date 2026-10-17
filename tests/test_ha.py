from __future__ import annotations

import json
from typing import Any

import pytest

from app.config import EntityConfig
from app.ha import HomeAssistantClient


class FakeSocket:
    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self.messages = [json.dumps(message) for message in messages]
        self.sent: list[str] = []

    async def recv(self) -> str:
        return self.messages.pop(0)

    async def send(self, message: str) -> None:
        self.sent.append(message)


class FakeConnection:
    def __init__(self, socket: FakeSocket) -> None:
        self.socket = socket

    async def __aenter__(self) -> FakeSocket:
        return self.socket

    async def __aexit__(self, *args: object) -> None:
        return None


def entity_config() -> EntityConfig:
    return EntityConfig(
        pit_climate="climate.grill",
        pit_temp="sensor.pit",
        probe1_temp="sensor.probe_1",
        probe2_temp="sensor.probe_2",
        probe1_connection="binary_sensor.probe_1",
        probe2_connection="binary_sensor.probe_2",
        probe1_climate="climate.probe_1",
        probe2_climate="climate.probe_2",
        fire_state="sensor.fire",
        power_state="sensor.power",
        warning="sensor.warning",
        extra_probes=("sensor.extra_probe",),
    )


@pytest.mark.asyncio
async def test_large_get_states_payload_connects_and_keeps_configured_entities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entities = entity_config()
    result = [
        {"entity_id": f"sensor.dummy_{index}", "state": "x" * 300}
        for index in range(4_000)
    ]
    result.extend(
        [
            {
                "entity_id": entities.pit_climate,
                "state": "heat",
                "attributes": {"temperature": 275},
            },
            {"entity_id": entities.pit_temp, "state": "250"},
            {"entity_id": entities.extra_probes[0], "state": "165"},
        ]
    )
    payload = {"id": 1, "type": "result", "success": True, "result": result}
    assert len(json.dumps(payload)) > 1_048_576
    socket = FakeSocket([{"type": "auth_required"}, {"type": "auth_ok"}, payload])
    connect_args: dict[str, Any] = {}

    def connect(url: str, **kwargs: Any) -> FakeConnection:
        connect_args.update(url=url, **kwargs)
        return FakeConnection(socket)

    monkeypatch.setattr("app.ha.websockets.connect", connect)
    client = HomeAssistantClient("http://ha", "token", entities)

    snapshot = await anext(client._connected())

    assert connect_args["max_size"] == 67_108_864
    assert snapshot.pit_temp == 250
    assert snapshot.setpoint == 275
    assert snapshot.extra_probes == {"sensor.extra_probe": 165}
    assert client.status.connected is True


@pytest.mark.asyncio
async def test_unconfigured_state_changed_entity_is_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entities = entity_config()
    messages = [
        {"type": "auth_required"},
        {"type": "auth_ok"},
        {
            "id": 1,
            "type": "result",
            "success": True,
            "result": [{"entity_id": entities.pit_temp, "state": "250"}],
        },
        {
            "id": 2,
            "type": "event",
            "event": {
                "data": {
                    "entity_id": "sensor.not_configured",
                    "new_state": {"entity_id": "sensor.not_configured", "state": "999"},
                }
            },
        },
        {
            "id": 2,
            "type": "event",
            "event": {
                "data": {
                    "entity_id": entities.pit_temp,
                    "new_state": {"entity_id": entities.pit_temp, "state": "251"},
                }
            },
        },
    ]
    socket = FakeSocket(messages)
    monkeypatch.setattr("app.ha.websockets.connect", lambda *args, **kwargs: FakeConnection(socket))
    snapshots = HomeAssistantClient("http://ha", "token", entities)._connected()

    initial = await anext(snapshots)
    updated = await anext(snapshots)

    assert initial.pit_temp == 250
    assert updated.pit_temp == 251


def test_unconfigured_entities_are_dropped_from_full_state_results() -> None:
    entities = entity_config()
    client = HomeAssistantClient("http://ha", "token", entities)

    states = client._configured_states(
        [
            {"entity_id": entities.pit_temp, "state": "250"},
            {"entity_id": "sensor.not_configured", "state": "999"},
        ]
    )

    assert states == {entities.pit_temp: {"entity_id": entities.pit_temp, "state": "250"}}


def test_snapshot_reads_climate_attributes_and_real_probe_connections() -> None:
    entities = EntityConfig(
        pit_climate="climate.green_mountain_grill",
        pit_temp="sensor.green_mountain_grill_temperature",
        probe1_temp="sensor.green_mountain_grill_probe_1_temperature",
        probe2_temp="sensor.green_mountain_grill_probe_2_temperature",
        probe1_connection="binary_sensor.green_mountain_grill_probe_1_connection",
        probe2_connection="binary_sensor.green_mountain_grill_probe_2_connection",
        probe1_climate="climate.green_mountain_grill_probe_1",
        probe2_climate="climate.green_mountain_grill_probe_2",
        fire_state="sensor.green_mountain_grill_fire_state",
        power_state="sensor.green_mountain_grill_power_state",
        warning="sensor.green_mountain_grill_warning",
    )
    states: dict[str, dict[str, Any]] = {
        entities.pit_climate: {"state": "heat", "attributes": {"temperature": 275}},
        entities.pit_temp: {"state": "250"},
        entities.probe1_temp: {"state": "160"},
        entities.probe2_temp: {"state": "unknown"},
        entities.probe1_connection: {"state": "on"},
        entities.probe2_connection: {"state": "off"},
        entities.probe1_climate: {"state": "heat", "attributes": {"temperature": 203}},
        entities.probe2_climate: {"state": "off", "attributes": {"temperature": 165}},
        entities.fire_state: {"state": "Running"},
        entities.power_state: {"state": "On"},
        entities.warning: {"state": "None"},
    }

    snapshot = HomeAssistantClient("http://ha", "token", entities)._snapshot(states)

    assert snapshot.setpoint == 275
    assert snapshot.probe1_target == 203
    assert snapshot.probe2_target == 165
    assert snapshot.probe1_connected
    assert not snapshot.probe2_connected
    assert snapshot.probe2 is None
