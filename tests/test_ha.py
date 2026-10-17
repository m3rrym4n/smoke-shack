from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import pytest
from conftest import FakeClock
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import EntityConfig
from app.ha import HAStatus, HomeAssistantClient, ingest, parse_device_template
from app.models import Cook, Event, Sample
from app.service import CookService, GrillSnapshot


class FakeSocket:
    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self.messages = [json.dumps(message) for message in messages]
        self.sent: list[str] = []

    async def recv(self) -> str:
        if not self.messages:
            await asyncio.Future()
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


class SnapshotSource:
    def __init__(self, initial: GrillSnapshot) -> None:
        self.initial = initial
        self.status = HAStatus(configured=True, connected=True)
        self.updates: asyncio.Queue[GrillSnapshot] = asyncio.Queue()

    async def snapshots(self) -> AsyncIterator[GrillSnapshot]:
        yield self.initial
        while True:
            yield await self.updates.get()


class ControlledSleep:
    def __init__(self) -> None:
        self.ticks: asyncio.Queue[None] = asyncio.Queue()

    async def __call__(self, _seconds: float) -> None:
        await self.ticks.get()


async def wait_for_samples(sessions: sessionmaker[Session], count: int) -> None:
    for _ in range(100):
        with sessions() as session:
            if len(list(session.scalars(select(Sample)))) == count:
                return
        await asyncio.sleep(0)
    pytest.fail(f"timed out waiting for {count} samples")


def cooking_snapshot(pit_temp: float = 250) -> GrillSnapshot:
    return GrillSnapshot(
        pit_temp=pit_temp,
        setpoint=275,
        fire_state="Running",
        power_state="On",
        hvac_mode="heat",
    )


@pytest.mark.asyncio
async def test_sample_tick_records_each_interval_without_events(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    source = SnapshotSource(cooking_snapshot())
    sleeper = ControlledSleep()
    task = asyncio.create_task(ingest(source, CookService(sessions, clock, 10), 10, sleeper))
    await wait_for_samples(sessions, 1)

    for expected in range(2, 5):
        clock.advance(seconds=10)
        sleeper.ticks.put_nowait(None)
        await wait_for_samples(sessions, expected)

    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_disconnected_tick_skips_samples_and_next_snapshot_records_gap(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    source = SnapshotSource(cooking_snapshot())
    sleeper = ControlledSleep()
    task = asyncio.create_task(ingest(source, CookService(sessions, clock, 10), 10, sleeper))
    await wait_for_samples(sessions, 1)

    source.status.connected = False
    clock.advance(seconds=31)
    sleeper.ticks.put_nowait(None)
    await asyncio.sleep(0)
    with sessions() as session:
        assert len(list(session.scalars(select(Sample)))) == 1

    source.status.connected = True
    source.updates.put_nowait(cooking_snapshot(251))
    await wait_for_samples(sessions, 2)
    with sessions() as session:
        cook = session.scalar(select(Cook))
        gap = session.scalar(select(Event).where(Event.kind == "data_gap"))
        assert cook is not None and cook.has_gap
        assert gap is not None

    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_event_and_tick_do_not_sample_twice_within_interval(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    source = SnapshotSource(cooking_snapshot())
    sleeper = ControlledSleep()
    task = asyncio.create_task(ingest(source, CookService(sessions, clock, 10), 10, sleeper))
    await wait_for_samples(sessions, 1)

    clock.advance(seconds=5)
    source.updates.put_nowait(cooking_snapshot(251))
    await asyncio.sleep(0)
    clock.advance(seconds=5)
    sleeper.ticks.put_nowait(None)
    await wait_for_samples(sessions, 2)

    with sessions() as session:
        samples = list(session.scalars(select(Sample).order_by(Sample.ts)))
    assert samples[1].ts - samples[0].ts == timedelta(seconds=10)

    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


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
    result = [{"entity_id": f"sensor.dummy_{index}", "state": "x" * 300} for index in range(4_000)]
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
    snapshots = HomeAssistantClient(
        "http://ha", "token", entities, coalesce_window_seconds=0.01
    )._connected()

    initial = await anext(snapshots)
    updated = await anext(snapshots)

    assert initial.pit_temp == 250
    assert updated.pit_temp == 251


@pytest.mark.asyncio
async def test_entity_update_burst_is_coalesced(monkeypatch: pytest.MonkeyPatch) -> None:
    entities = entity_config()
    initial_states = [
        {"entity_id": entities.pit_climate, "state": "heat", "attributes": {"temperature": 150}},
        {"entity_id": entities.pit_temp, "state": "100"},
        {"entity_id": entities.fire_state, "state": "Startup"},
        {"entity_id": entities.power_state, "state": "On"},
        {"entity_id": entities.warning, "state": "None"},
        {"entity_id": entities.probe2_connection, "state": "off"},
    ]
    updates = [
        (entities.pit_climate, "off", {"temperature": 65535}),
        (entities.pit_temp, "65535", {}),
        (entities.fire_state, "Off", {}),
        (entities.power_state, "Off", {}),
        (entities.warning, "Unknown", {}),
        (entities.probe2_connection, "on", {}),
    ]
    messages: list[dict[str, Any]] = [
        {"type": "auth_required"},
        {"type": "auth_ok"},
        {"id": 1, "type": "result", "success": True, "result": initial_states},
    ]
    messages.extend(
        {
            "id": 2,
            "type": "event",
            "event": {
                "data": {
                    "entity_id": entity_id,
                    "new_state": {
                        "entity_id": entity_id,
                        "state": state,
                        "attributes": attributes,
                    },
                }
            },
        }
        for entity_id, state, attributes in updates
    )
    socket = FakeSocket(messages)
    monkeypatch.setattr("app.ha.websockets.connect", lambda *args, **kwargs: FakeConnection(socket))
    snapshots = HomeAssistantClient(
        "http://ha", "token", entities, coalesce_window_seconds=0.01
    )._connected()

    await anext(snapshots)
    coalesced = await anext(snapshots)

    assert coalesced.setpoint == 65535
    assert coalesced.pit_temp == 65535
    assert coalesced.hvac_mode == "off"
    assert coalesced.warning == "Unknown"
    assert coalesced.probe2_connected


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
        entities.pit_climate: {
            "state": "heat",
            "attributes": {"temperature": 275, "friendly_name": "Daniel Boone Prime"},
        },
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
    assert snapshot.grill_name == "Daniel Boone Prime"
    assert snapshot.probe1_target == 203
    assert snapshot.probe2_target == 165
    assert snapshot.probe1_connected
    assert not snapshot.probe2_connected
    assert snapshot.probe2 is None


@pytest.mark.asyncio
async def test_ingest_caches_last_grill_name_when_ha_state_loses_it(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    source = SnapshotSource(
        GrillSnapshot(
            grill_name="Daniel Boone",
            setpoint=275,
            fire_state="Running",
            power_state="On",
            hvac_mode="heat",
        )
    )
    sleeper = ControlledSleep()
    task = asyncio.create_task(ingest(source, CookService(sessions, clock), 10, sleeper))
    await wait_for_samples(sessions, 1)
    assert source.status.grill_name == "Daniel Boone"

    source.updates.put_nowait(
        GrillSnapshot(
            setpoint=275,
            fire_state="Running",
            power_state="On",
            hvac_mode="heat",
        )
    )
    for _ in range(100):
        await asyncio.sleep(0)
        if source.updates.empty():
            break
    assert source.status.grill_name == "Daniel Boone"

    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        (
            "Daniel Boone|Green Mountain Grills|Backyard Beast",
            ("Daniel Boone", "Green Mountain Grills", "Backyard Beast"),
        ),
        ("None| None |None\n", (None, None, None)),
        ("  |Green Mountain Grills| ", (None, "Green Mountain Grills", None)),
    ],
)
def test_parse_device_template_fields_and_none(
    output: str, expected: tuple[str | None, str | None, str | None]
) -> None:
    assert parse_device_template(output) == expected


@pytest.mark.parametrize("output", ["", "garbage", "model|maker", "a|b|c|d"])
def test_parse_device_template_rejects_empty_or_garbage(output: str) -> None:
    with pytest.raises(ValueError):
        parse_device_template(output)


@pytest.mark.asyncio
async def test_device_template_prefers_user_name_then_model_and_caches_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = HomeAssistantClient("http://ha", "secret", entity_config())
    outputs = iter(
        [
            "Daniel Boone|Green Mountain Grills|Backyard Beast",
            "Daniel Boone|Green Mountain Grills|None",
        ]
    )
    monkeypatch.setattr(client, "_read_template", lambda _request: next(outputs))

    await client._refresh_device_info()
    assert client.status.grill_title == "Backyard Beast"
    assert client.status.grill_maker == "Green Mountain Grills"

    await client._refresh_device_info()
    assert client.status.grill_title == "Daniel Boone"

    def fail(_request: object) -> str:
        raise OSError("HA unavailable")

    monkeypatch.setattr(client, "_read_template", fail)
    await client._refresh_device_info()
    assert client.status.grill_title == "Daniel Boone"
    assert client.status.grill_maker == "Green Mountain Grills"
