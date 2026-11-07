from __future__ import annotations

import pytest
from conftest import FakeClock, add_channels
from sqlalchemy import event, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Channel, ChannelReading, Sample
from app.service import CookService, GrillSnapshot


def readings_by_key(session: Session) -> dict[str, tuple[float | None, float | None]]:
    rows = session.execute(
        select(Channel.key, ChannelReading.value, ChannelReading.target)
        .join(ChannelReading, ChannelReading.channel_id == Channel.id)
        .order_by(Channel.position)
    )
    return {key: (value, target) for key, value, target in rows}


def test_sample_records_legacy_columns_and_channel_readings(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    add_channels(sessions)
    snapshot = GrillSnapshot(
        pit_temp=250,
        setpoint=275,
        probe1=150,
        probe1_target=203,
        fire_state="Running",
        power_state="On",
        hvac_mode="heat",
    )

    CookService(sessions, clock).process(snapshot)

    with sessions() as session:
        sample = session.scalars(select(Sample)).one()
        assert (sample.pit_temp, sample.setpoint) == (250, 275)
        assert (sample.probe1, sample.probe1_target) == (150, 203)
        assert readings_by_key(session) == {
            "pit": (250, 275),
            "probe1": (150, 203),
        }


def test_masterbuilt_snapshot_records_five_channels(
    sessions: sessionmaker[Session],
    clock: FakeClock,
    masterbuilt_gravity_800_snapshot: GrillSnapshot,
) -> None:
    add_channels(sessions, ("pit", "probe1", "probe2", "probe3", "probe4"))

    CookService(sessions, clock).process(masterbuilt_gravity_800_snapshot)

    with sessions() as session:
        assert readings_by_key(session) == {
            "pit": (300, 300),
            "probe1": (155, 195),
            "probe2": (160, 200),
            "probe3": (165, 205),
            "probe4": (170, 210),
        }


def test_missing_probe_does_not_record_a_reading(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    add_channels(sessions)
    snapshot = GrillSnapshot(
        pit_temp=250,
        setpoint=275,
        probe1=150,
        probe1_target=203,
        fire_state="Running",
        power_state="On",
        hvac_mode="heat",
    )

    CookService(sessions, clock).process(snapshot)

    with sessions() as session:
        assert "probe2" not in readings_by_key(session)


def test_reading_failure_rolls_back_sample(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    add_channels(sessions)

    def fail_reading_write(*_args: object) -> None:
        raise RuntimeError("forced reading failure")

    event.listen(ChannelReading, "before_insert", fail_reading_write)
    try:
        with pytest.raises(RuntimeError, match="forced reading failure"):
            CookService(sessions, clock).process(
                GrillSnapshot(
                    pit_temp=250,
                    setpoint=275,
                    fire_state="Running",
                    power_state="On",
                    hvac_mode="heat",
                )
            )
    finally:
        event.remove(ChannelReading, "before_insert", fail_reading_write)

    with sessions() as session:
        assert session.scalar(select(Sample.id)) is None
        assert session.scalar(select(ChannelReading.id)) is None
