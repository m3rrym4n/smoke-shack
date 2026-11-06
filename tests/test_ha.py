from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
import yaml
from alembic import command
from alembic.config import Config
from conftest import FakeClock
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import EntityConfig
from app.database import make_engine, make_session_factory
from app.grill_profiles import load_grill_profiles
from app.ha import HARegistrySnapshot, HAStatus, HomeAssistantClient, ingest, parse_device_template
from app.models import Channel, ChannelReading, Cook, Equipment, EquipmentEntity, Event, Sample
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
        gap = session.scalar(select(Event).where(Event.kind == "data_gap_summary"))
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


def set_connected_channels(
    sessions: sessionmaker[Session],
    channels: list[tuple[str, str, str | None]],
) -> int:
    with sessions() as session:
        equipment = session.query(Equipment).one()
        equipment.channels = [
            Channel(
                key=key,
                role="pit" if key == "pit" else "meat",
                label=key.title(),
                source_entity=source,
                target_entity=target,
                position=position,
            )
            for position, (key, source, target) in enumerate(channels)
        ]
        session.commit()
        return equipment.id


def migrated_equipment_sessions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entities: EntityConfig
) -> sessionmaker[Session]:
    database = tmp_path / "migrated-equipment.db"
    entities_path = tmp_path / "entities.yaml"
    entities_path.write_text(yaml.safe_dump(entities.__dict__))
    monkeypatch.setenv("DATABASE_PATH", str(database))
    monkeypatch.setenv("ENTITIES_CONFIG", str(entities_path))
    command.upgrade(Config("alembic.ini"), "head")
    return make_session_factory(make_engine(str(database)))


def test_connected_masterbuilt_channels_build_snapshot_and_watch_list(
    sessions: sessionmaker[Session],
) -> None:
    channels = [
        ("pit", "sensor.mb_pit", "sensor.mb_target"),
        *[
            (f"probe{number}", f"sensor.mb_probe{number}", f"sensor.mb_probe{number}_target")
            for number in range(1, 5)
        ],
    ]
    set_connected_channels(sessions, channels)
    client = HomeAssistantClient("http://ha", "token", entity_config(), sessions=sessions)

    assert client.refresh_watch_list()
    assert not client._is_legacy(client._equipment)
    assert client.entity_ids == {
        entity for _, source, target in channels for entity in (source, target) if entity
    }
    snapshot = client._snapshot(
        {
            entity: {"entity_id": entity, "state": str(value)}
            for value, entity in enumerate(sorted(client.entity_ids), start=100)
        }
    )

    assert snapshot.pit_temp is not None
    assert snapshot.setpoint is not None
    assert set(snapshot.extra_probes) == {"probe3", "probe4"}
    assert set(snapshot.extra_probe_targets) == {"probe3", "probe4"}
    assert snapshot.fire_state is None
    assert snapshot.power_state is None
    assert snapshot.hvac_mode is None
    assert not snapshot.cook_lifecycle_enabled


def test_switching_connected_equipment_refreshes_watch_list(
    sessions: sessionmaker[Session],
) -> None:
    first_id = set_connected_channels(sessions, [("pit", "sensor.first", None)])
    client = HomeAssistantClient("http://ha", "token", entity_config(), sessions=sessions)
    client.refresh_watch_list()
    assert client.entity_ids == {"sensor.first"}

    with sessions() as session:
        first = session.get(Equipment, first_id)
        assert first is not None
        first.connected = False
        second = Equipment(nickname="Second", type="pellet", units="F", connected=True)
        second.channels = [
            Channel(
                key="pit",
                role="pit",
                label="Pit",
                source_entity="sensor.second",
                position=0,
            )
        ]
        session.add(second)
        session.commit()

    assert client.refresh_watch_list()
    assert client.entity_ids == {"sensor.second"}


def test_connected_equipment_status_entities_are_watched(sessions) -> None:
    equipment_id = set_connected_channels(sessions, [("pit", "sensor.mb_pit", None)])
    with sessions() as session:
        equipment = session.get(Equipment, equipment_id)
        assert equipment is not None
        equipment.stale_after_seconds = 600
        equipment.entities = [
            EquipmentEntity(role="power", entity_id="binary_sensor.mb_power"),
            EquipmentEntity(role="last_reported", entity_id="sensor.mb_last_reported"),
        ]
        session.commit()
    client = HomeAssistantClient("http://ha", "token", entity_config(), sessions=sessions)

    assert client.refresh_watch_list()
    assert client.entity_ids == {
        "sensor.mb_pit",
        "binary_sensor.mb_power",
        "sensor.mb_last_reported",
    }
    assert client._equipment is not None
    assert client._equipment.status_entities == {
        "power": "binary_sensor.mb_power",
        "last_reported": "sensor.mb_last_reported",
    }
    assert client._equipment.stale_after_seconds == 600


def masterbuilt_registry_snapshot() -> HARegistrySnapshot:
    entity_specs = (
        ("sensor.mb_pit", "grill_temp"),
        ("binary_sensor.mb_power", "power"),
        ("binary_sensor.mb_heating", "heating"),
        ("binary_sensor.mb_lid_open", "lid_open"),
        ("binary_sensor.mb_door_open", "door_open"),
        ("binary_sensor.mb_problem", "problem"),
        ("sensor.mb_last_reported", "last_reported"),
        ("sensor.mb_cook_start", "cook_start"),
    )
    return HARegistrySnapshot(
        devices=(
            {
                "id": "masterbuilt-device",
                "manufacturer": "Masterbuilt",
                "model": "Gravity Series 800",
            },
        ),
        entities=tuple(
            {
                "device_id": "masterbuilt-device",
                "entity_id": entity_id,
                "unique_id": f"masterbuilt_{role}",
            }
            for entity_id, role in entity_specs
        ),
        states=(),
    )


def client_needing_status_backfill(sessions: sessionmaker[Session]) -> HomeAssistantClient:
    set_connected_channels(sessions, [("pit", "sensor.mb_pit", None)])
    return HomeAssistantClient(
        "http://ha",
        "token",
        entity_config(),
        sessions=sessions,
        grill_profiles=load_grill_profiles("config/grill_profiles"),
    )


@pytest.mark.asyncio
async def test_refresh_backfills_status_entities_before_building_watch_list_and_starts_cook(
    sessions: sessionmaker[Session], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO", logger="app.ha")
    client = client_needing_status_backfill(sessions)
    client.registry_snapshot = AsyncMock(return_value=masterbuilt_registry_snapshot())

    assert await client._refresh_watch_list()

    expected_status_entities = {
        "binary_sensor.mb_power",
        "binary_sensor.mb_heating",
        "binary_sensor.mb_lid_open",
        "binary_sensor.mb_door_open",
        "binary_sensor.mb_problem",
        "sensor.mb_last_reported",
        "sensor.mb_cook_start",
    }
    assert expected_status_entities < client.entity_ids
    with sessions() as session:
        equipment = session.query(Equipment).one()
        assert {entity.entity_id for entity in equipment.entities} == expected_status_entities
        assert equipment.stale_after_seconds == 600
    assert "Filled status entities for connected equipment" in caplog.text

    reading = client._snapshot(
        {
            "sensor.mb_pit": {"entity_id": "sensor.mb_pit", "state": "275"},
            "binary_sensor.mb_power": {
                "entity_id": "binary_sensor.mb_power",
                "state": "on",
            },
            "binary_sensor.mb_problem": {
                "entity_id": "binary_sensor.mb_problem",
                "state": "off",
            },
            "sensor.mb_last_reported": {
                "entity_id": "sensor.mb_last_reported",
                "state": datetime.now(UTC).isoformat(),
            },
        }
    )
    cook = CookService(sessions, sample_interval_seconds=10).process(reading)
    assert cook is not None


@pytest.mark.asyncio
async def test_status_backfill_retries_after_home_assistant_is_unreachable(sessions) -> None:
    client = client_needing_status_backfill(sessions)
    client.registry_snapshot = AsyncMock(side_effect=RuntimeError("connection refused"))

    assert client.refresh_watch_list()
    await client._backfill_status_entities()
    with sessions() as session:
        equipment = session.query(Equipment).one()
        assert equipment.entities == []
        assert equipment.stale_after_seconds is None

    client.registry_snapshot = AsyncMock(return_value=masterbuilt_registry_snapshot())
    await client._refresh_watch_list()
    assert "binary_sensor.mb_power" in client.entity_ids


@pytest.mark.asyncio
async def test_status_backfill_leaves_existing_and_entities_yaml_equipment_untouched(
    sessions,
) -> None:
    equipment_id = set_connected_channels(sessions, [("pit", "sensor.mb_pit", None)])
    with sessions() as session:
        equipment = session.get(Equipment, equipment_id)
        assert equipment is not None
        equipment.entities = [
            EquipmentEntity(role=role, entity_id=f"sensor.saved_{role}")
            for role in (
                "power",
                "heating",
                "lid_open",
                "door_open",
                "error",
                "last_reported",
                "cook_start",
            )
        ]
        equipment.stale_after_seconds = 123
        session.commit()
    client = HomeAssistantClient(
        "http://ha",
        "token",
        entity_config(),
        sessions=sessions,
        grill_profiles=load_grill_profiles("config/grill_profiles"),
    )
    client.registry_snapshot = AsyncMock(return_value=masterbuilt_registry_snapshot())

    await client._refresh_watch_list()
    client.registry_snapshot.assert_not_awaited()
    with sessions() as session:
        equipment = session.get(Equipment, equipment_id)
        assert equipment is not None
        assert {entity.role: entity.entity_id for entity in equipment.entities}["power"] == (
            "sensor.saved_power"
        )
        assert equipment.stale_after_seconds == 123

    with sessions() as session:
        equipment = session.get(Equipment, equipment_id)
        assert equipment is not None
        equipment.entities = []
        equipment.channels[0].source_entity = entity_config().pit_temp
        session.commit()
    client.registry_snapshot.reset_mock()
    await client._refresh_watch_list()
    client.registry_snapshot.assert_not_awaited()
    with sessions() as session:
        equipment = session.get(Equipment, equipment_id)
        assert equipment is not None
        assert equipment.entities == []


def masterbuilt_client(
    sessions: sessionmaker[Session], clock: FakeClock | None = None
) -> tuple[HomeAssistantClient, int]:
    channels = [
        ("pit", "sensor.masterbuilt_grill_temp", "sensor.masterbuilt_setpoint"),
        *(
            (f"probe{number}", f"sensor.masterbuilt_probe{number}_temp", None)
            for number in range(1, 5)
        ),
    ]
    equipment_id = set_connected_channels(sessions, channels)
    with sessions() as session:
        equipment = session.get(Equipment, equipment_id)
        assert equipment is not None
        equipment.entities = [
            EquipmentEntity(role="power", entity_id="binary_sensor.masterbuilt_power"),
            EquipmentEntity(role="error", entity_id="binary_sensor.masterbuilt_problem"),
            EquipmentEntity(role="last_reported", entity_id="sensor.masterbuilt_last_reported"),
        ]
        equipment.stale_after_seconds = 600
        session.commit()
    client = HomeAssistantClient(
        "http://ha",
        "token",
        entity_config(),
        sessions=sessions,
        clock=clock.now if clock is not None else None,
    )
    client.refresh_watch_list()
    return client, equipment_id


def masterbuilt_states(
    power: str, error: str = "off", last_reported: str | None = None
) -> dict[str, dict[str, Any]]:
    last_reported = last_reported or datetime.now(UTC).isoformat()
    values = {
        "binary_sensor.masterbuilt_power": power,
        "binary_sensor.masterbuilt_problem": error,
        "sensor.masterbuilt_last_reported": last_reported,
        "sensor.masterbuilt_grill_temp": "700",
        "sensor.masterbuilt_setpoint": "700",
        **{f"sensor.masterbuilt_probe{number}_temp": str(150 + number) for number in range(1, 5)},
    }
    return {entity: {"entity_id": entity, "state": value} for entity, value in values.items()}


def test_masterbuilt_stale_snapshot_clears_all_telemetry_and_recovers(
    sessions: sessionmaker[Session], clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO", logger="app.ha")
    client, _ = masterbuilt_client(sessions, clock)

    states = masterbuilt_states("on", last_reported=clock.now().isoformat())
    fresh = client._snapshot(states)
    assert (fresh.pit_temp, fresh.setpoint, fresh.power_state, fresh.warning) == (
        700,
        700,
        "On",
        "None",
    )

    clock.advance(seconds=601)
    stale = client._snapshot(states)
    assert stale.stale is True
    assert stale.pit_temp is stale.setpoint is stale.power_state is stale.hvac_mode is None
    assert stale.fire_state is stale.warning is stale.probe1_target is stale.probe2_target is None
    assert all(value is None for value in stale.extra_probes.values())

    recovered = client._snapshot(
        masterbuilt_states("on", last_reported=clock.now().isoformat())
    )
    assert recovered.pit_temp == 700
    assert caplog.text.count("telemetry is stale") == 1
    assert caplog.text.count("telemetry is fresh") == 1


def test_stale_masterbuilt_snapshots_do_not_replace_change_baseline(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    service = CookService(sessions, clock)
    fresh = GrillSnapshot(
        pit_temp=225,
        setpoint=225,
        probe1=150,
        probe1_connected=True,
        fire_state="Running",
        power_state="On",
        hvac_mode="heat",
        startup_ends_at_setpoint=True,
    )
    cook = service.process(fresh)
    assert cook is not None

    for _ in range(3):
        clock.advance(seconds=10)
        service.process(GrillSnapshot(stale=True, startup_ends_at_setpoint=True))
    clock.advance(seconds=10)
    cook = service.process(fresh)

    assert cook is not None and cook.ended_at is None
    with sessions() as session:
        change_events = list(
            session.scalars(
                select(Event).where(
                    Event.cook_id == cook.id,
                    Event.kind.in_(
                        {
                            "setpoint_changed",
                            "mode_changed",
                            "probe_connected",
                            "probe_disconnected",
                        }
                    ),
                )
            )
        )
    assert change_events == []


def test_fresh_masterbuilt_change_after_stale_snapshots_is_recorded_once(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    service = CookService(sessions, clock)
    fresh = GrillSnapshot(
        pit_temp=225,
        setpoint=225,
        probe1=150,
        probe1_connected=True,
        fire_state="Running",
        power_state="On",
        hvac_mode="heat",
        startup_ends_at_setpoint=True,
    )
    cook = service.process(fresh)
    assert cook is not None

    for _ in range(3):
        clock.advance(seconds=10)
        service.process(GrillSnapshot(stale=True, startup_ends_at_setpoint=True))
    clock.advance(seconds=10)
    service.process(GrillSnapshot(**{**fresh.__dict__, "setpoint": 250}))

    with sessions() as session:
        events = list(
            session.scalars(
                select(Event).where(
                    Event.cook_id == cook.id,
                    Event.kind == "setpoint_changed",
                )
            )
        )
    assert len(events) == 1
    assert events[0].data == {"from": 225, "to": 250}


def test_restart_after_empty_sample_uses_no_change_baseline(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    fresh = GrillSnapshot(
        pit_temp=225,
        setpoint=225,
        probe1=150,
        probe1_connected=True,
        fire_state="Running",
        power_state="On",
        hvac_mode="heat",
        startup_ends_at_setpoint=True,
    )
    service = CookService(sessions, clock)
    cook = service.process(fresh)
    assert cook is not None
    clock.advance(seconds=10)
    service.process(GrillSnapshot(stale=True, startup_ends_at_setpoint=True))

    clock.advance(seconds=10)
    CookService(sessions, clock).process(fresh)

    with sessions() as session:
        change_events = list(
            session.scalars(
                select(Event).where(
                    Event.cook_id == cook.id,
                    Event.kind.in_(
                        {
                            "setpoint_changed",
                            "mode_changed",
                            "probe_connected",
                            "probe_disconnected",
                        }
                    ),
                )
            )
        )
    assert change_events == []


@pytest.mark.parametrize("last_reported", ["unknown", "unavailable"])
def test_masterbuilt_unknown_last_reported_is_stale(
    sessions: sessionmaker[Session], clock: FakeClock, last_reported: str
) -> None:
    client, _ = masterbuilt_client(sessions, clock)
    assert client._snapshot(masterbuilt_states("on", last_reported=last_reported)).pit_temp is None


def test_masterbuilt_unparseable_last_reported_stays_fresh_and_warns_once(
    sessions: sessionmaker[Session], clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("WARNING", logger="app.ha")
    client, _ = masterbuilt_client(sessions, clock)

    assert client._snapshot(masterbuilt_states("on", last_reported="not-a-date")).pit_temp == 700
    assert client._snapshot(masterbuilt_states("on", last_reported="still-bad")).pit_temp == 700
    assert caplog.text.count("not an ISO timestamp") == 1


def test_masterbuilt_without_last_reported_is_never_stale(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    client, _ = masterbuilt_client(sessions, clock)
    assert client._equipment is not None
    client._equipment.status_entities.pop("last_reported")
    clock.advance(hours=24)
    assert client._snapshot(masterbuilt_states("on")).pit_temp == 700


def test_stale_masterbuilt_does_not_change_or_timeout_cook(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    client, _ = masterbuilt_client(sessions, clock)
    service = CookService(sessions, clock, incomplete_timeout_minutes=1)
    states = masterbuilt_states("on", last_reported=clock.now().isoformat())
    cook = service.process(client._snapshot(states))
    assert cook is not None

    clock.advance(minutes=11)
    states["binary_sensor.masterbuilt_power"]["state"] = "off"
    stale = client._snapshot(states)
    cook = service.process(stale)

    assert cook is not None and cook.ended_at is None and cook.status == "cook"
    with sessions() as session:
        samples = list(session.scalars(select(Sample).where(Sample.cook_id == cook.id)))
        phase_events = list(
            session.scalars(
                select(Event).where(Event.cook_id == cook.id, Event.kind == "phase_changed")
            )
        )
    assert len(samples) == 2 and samples[-1].pit_temp is None
    assert len(phase_events) == 2


def test_masterbuilt_staleness_is_rebuilt_on_tick_without_event(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    client, _ = masterbuilt_client(sessions, clock)
    client._last_states = masterbuilt_states("on", last_reported=clock.now().isoformat())
    fresh = client._snapshot(client._last_states)
    assert client.snapshot_on_tick(fresh).pit_temp == 700

    clock.advance(seconds=601)
    assert client.snapshot_on_tick(fresh).pit_temp is None


def test_masterbuilt_power_drives_cook_lifecycle_and_records_equipment(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    client, equipment_id = masterbuilt_client(sessions)
    service = CookService(sessions, clock)

    assert service.process(client._snapshot(masterbuilt_states("off"))) is None
    started = service.process(client._snapshot(masterbuilt_states("on", "on")))
    assert started is not None and started.status == "cook"
    assert started.equipment_id == equipment_id

    clock.advance(seconds=10)
    closed = service.process(client._snapshot(masterbuilt_states("off")))
    assert closed is not None and closed.status == "closed"
    with sessions() as session:
        samples = list(session.scalars(select(Sample).where(Sample.cook_id == closed.id)))
        reading_equipment_ids = set(
            session.scalars(
                select(Channel.equipment_id)
                .join(ChannelReading, ChannelReading.channel_id == Channel.id)
                .where(ChannelReading.sample_id.in_([sample.id for sample in samples]))
            )
        )
        phase_titles = list(
            session.scalars(
                select(Event.title).where(Event.cook_id == closed.id, Event.kind == "phase_changed")
            )
        )
    assert samples[0].pit_temp == 700
    assert reading_equipment_ids == {equipment_id}
    assert "Cool down started" in phase_titles
    assert "Cook closed" in phase_titles


@pytest.mark.parametrize("power", ["unknown", "unavailable"])
def test_unknown_masterbuilt_power_never_starts_or_closes_cook(
    sessions: sessionmaker[Session], clock: FakeClock, power: str
) -> None:
    client, _ = masterbuilt_client(sessions)
    service = CookService(sessions, clock)

    snapshot = client._snapshot(masterbuilt_states(power))
    assert snapshot.power_state is snapshot.hvac_mode is snapshot.fire_state is None
    assert service.process(snapshot) is None
    cook = service.process(client._snapshot(masterbuilt_states("on")))
    assert cook is not None
    clock.advance(seconds=10)
    cook = service.process(snapshot)
    assert cook is not None and cook.status == "cook" and cook.ended_at is None


def test_masterbuilt_mapping_and_temperature_limits(sessions: sessionmaker[Session]) -> None:
    client, _ = masterbuilt_client(sessions)
    snapshot = client._snapshot(masterbuilt_states("on", "on"))

    assert (snapshot.power_state, snapshot.hvac_mode, snapshot.fire_state) == (
        "On",
        "heat",
        "Running",
    )
    assert snapshot.warning == "Problem"
    assert snapshot.cook_lifecycle_enabled
    assert snapshot.startup_ends_at_setpoint
    assert (snapshot.max_setpoint, snapshot.max_pit_temperature) == (750, 750)
    assert snapshot.implausible_reason() is None
    assert client._snapshot(masterbuilt_states("off")).warning == "None"
    assert client._snapshot(masterbuilt_states("on", "unknown")).warning is None
    assert GrillSnapshot(pit_temp=700).implausible_reason() == "pit temperature 700 is invalid"
    assert GrillSnapshot(setpoint=700).implausible_reason() == "setpoint 700 is outside 100-550"


def test_connected_nonlegacy_grill_starts_no_cook_and_logs_once(
    sessions: sessionmaker[Session], clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO", logger="app.service")
    set_connected_channels(sessions, [("pit", "sensor.mb_pit", "sensor.mb_target")])
    client = HomeAssistantClient("http://ha", "token", entity_config(), sessions=sessions)
    client.refresh_watch_list()
    snapshot = client._snapshot(
        {
            "sensor.mb_pit": {"entity_id": "sensor.mb_pit", "state": "250"},
            "sensor.mb_target": {"entity_id": "sensor.mb_target", "state": "275"},
        }
    )
    service = CookService(sessions, clock)

    service.process(snapshot)
    service.process(snapshot)

    with sessions() as session:
        assert session.scalar(select(Cook.id)) is None
        assert session.scalar(select(Sample.id)) is None
    assert caplog.text.count("has no cook start/stop mapping") == 1


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


def test_snapshot_reads_connected_yaml_equipment_like_before(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    sessions = migrated_equipment_sessions(tmp_path, monkeypatch, entities)
    client = HomeAssistantClient("http://ha", "token", entities, sessions=sessions)
    client.refresh_watch_list()

    snapshot = client._snapshot(states)

    assert client._is_legacy(client._equipment)
    assert entities.pit_climate in client.entity_ids
    assert entities.probe1_climate in client.entity_ids
    assert entities.probe2_climate in client.entity_ids
    assert snapshot.setpoint == 275
    assert snapshot.grill_name == "Daniel Boone Prime"
    assert snapshot.probe1_target == 203
    assert snapshot.probe2_target == 165
    assert snapshot.probe1_connected
    assert not snapshot.probe2_connected
    assert snapshot.probe2 is None
    assert snapshot.fire_state == "Running"
    assert snapshot.power_state == "On"
    assert snapshot.warning == "None"
    assert snapshot.cook_lifecycle_enabled


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
