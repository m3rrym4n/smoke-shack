from __future__ import annotations

from datetime import timedelta

from conftest import FakeClock, FakeHAClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Cook, Event, Sample
from app.service import CookService, GrillSnapshot


def snap(
    *,
    setpoint: float = 150,
    power: str = "On",
    mode: str = "heat",
    fire: str = "Startup",
    probe1: float | None = None,
    probe1_connected: bool = False,
    probe1_target: float | None = None,
    probe2: float | None = None,
    probe2_connected: bool = False,
    probe2_target: float | None = None,
    warning: str = "None",
) -> GrillSnapshot:
    return GrillSnapshot(
        pit_temp=100,
        setpoint=setpoint,
        probe1=probe1,
        probe2=probe2,
        probe1_connected=probe1_connected,
        probe2_connected=probe2_connected,
        probe1_target=probe1_target,
        probe2_target=probe2_target,
        fire_state=fire,
        power_state=power,
        hvac_mode=mode,
        warning=warning,
    )


def kinds(sessions: sessionmaker[Session], cook_id: int) -> list[str]:
    with sessions() as session:
        return list(
            session.scalars(select(Event.kind).where(Event.cook_id == cook_id).order_by(Event.id))
        )


def test_normal_cook(sessions: sessionmaker[Session], clock: FakeClock) -> None:
    fake = FakeHAClient()
    assert fake.items == []
    service = CookService(sessions, clock)
    cook = service.process(snap())
    assert cook is not None and cook.status == "startup"
    clock.advance(minutes=5)
    service.process(snap(setpoint=275, fire="Running"))
    clock.advance(hours=2)
    service.process(snap(setpoint=275, power="Fan", mode="off", fire="Cool Down"))
    clock.advance(minutes=10)
    closed = service.process(snap(setpoint=275, power="Off", mode="off", fire="Off"))
    assert closed is not None
    assert closed.startup_duration_seconds == 300
    assert closed.cook_duration_seconds == 7200
    assert closed.cooldown_duration_seconds == 600
    assert closed.grill_duration_seconds == 8100
    assert closed.aggregate_setpoint == 275
    assert kinds(sessions, closed.id).count("phase_changed") == 4
    assert "fire_lit" in kinds(sessions, closed.id)


def test_zero_second_startup(sessions: sessionmaker[Session], clock: FakeClock) -> None:
    cook = CookService(sessions, clock).process(snap(setpoint=275))
    assert cook is not None
    assert cook.status == "cook"
    assert cook.startup_ended_at == cook.started_at
    assert cook.startup_duration_seconds == 0


def test_return_to_150_stays_in_cook(sessions: sessionmaker[Session], clock: FakeClock) -> None:
    service = CookService(sessions, clock)
    service.process(snap())
    clock.advance(seconds=10)
    service.process(snap(setpoint=275))
    clock.advance(seconds=10)
    cook = service.process(snap(setpoint=150))
    assert cook is not None and cook.status == "cook"
    assert kinds(sessions, cook.id).count("setpoint_changed") == 2


def test_fan_only(sessions: sessionmaker[Session], clock: FakeClock) -> None:
    service = CookService(sessions, clock)
    assert service.process(snap(power="Fan", mode="fan_only", fire="Off")) is None
    cook = service.process(snap(setpoint=275))
    assert cook is not None
    clock.advance(seconds=10)
    cook = service.process(snap(setpoint=275, mode="fan_only"))
    assert cook is not None and cook.status == "cook"
    assert "mode_changed" in kinds(sessions, cook.id)


def test_failed_light_off_waits_for_real_ignition(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    service = CookService(sessions, clock)
    assert service.process(snap(power="On", mode="heat", fire="Cool Down")) is None
    clock.advance(seconds=10)
    cook = service.process(snap(power="On", mode="heat", fire="Startup"))
    assert cook is not None and cook.status == "startup"


def test_restart_during_cooldown_opens_new_cook(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    service = CookService(sessions, clock)
    old_cook = service.process(snap(setpoint=275, fire="Running"))
    assert old_cook is not None
    clock.advance(seconds=10)
    service.process(snap(setpoint=275, power="Fan", mode="off", fire="Cool Down"))
    clock.advance(seconds=10)
    new_cook = service.process(snap(power="On", mode="heat", fire="Startup"))

    assert new_cook is not None and new_cook.id != old_cook.id
    assert new_cook.status == "startup"
    assert kinds(sessions, new_cook.id)[:2] == ["fire_lit", "phase_changed"]
    with sessions() as session:
        closed = session.get(Cook, old_cook.id)
        assert closed is not None and closed.status == "closed" and closed.incomplete


def test_single_stale_cooldown_sample_does_not_end_startup(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    service = CookService(sessions, clock)
    cook = service.process(snap())
    assert cook is not None
    clock.advance(seconds=10)
    cook = service.process(snap(fire="Cool Down"))
    assert cook is not None and cook.status == "startup"
    clock.advance(seconds=10)
    cook = service.process(snap(fire="Startup"))
    assert cook is not None and cook.status == "startup"


def test_ha_outage_creates_gap_without_interpolation(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    service = CookService(sessions, clock, sample_interval_seconds=10)
    cook = service.process(snap(setpoint=275))
    assert cook is not None
    clock.advance(seconds=31)
    cook = service.process(snap(setpoint=275))
    assert cook is not None and cook.has_gap
    with sessions() as session:
        samples = list(session.scalars(select(Sample).where(Sample.cook_id == cook.id)))
        gap = session.scalar(
            select(Event).where(Event.cook_id == cook.id, Event.kind == "data_gap")
        )
    assert len(samples) == 2
    assert gap is not None
    assert gap.data["end"] == "2026-10-16T16:57:34Z"


def test_restart_resumes_active_phase(sessions: sessionmaker[Session], clock: FakeClock) -> None:
    first = CookService(sessions, clock)
    cook = first.process(snap(setpoint=275))
    assert cook is not None
    clock.advance(minutes=20)
    second = CookService(sessions, clock)
    resumed = second.active_cook()
    assert resumed is not None and resumed.id == cook.id and resumed.status == "cook"
    processed = second.process(snap(setpoint=275))
    assert processed is not None and processed.started_at == cook.started_at


def test_aggregate_setpoint_and_override(sessions: sessionmaker[Session], clock: FakeClock) -> None:
    service = CookService(sessions, clock)
    cook = service.process(snap(setpoint=275))
    assert cook is not None
    clock.advance(hours=4)
    service.process(snap(setpoint=350))
    clock.advance(minutes=30)
    service.process(snap(setpoint=350, power="Fan", mode="off", fire="Cool Down"))
    clock.advance(minutes=5)
    closed = service.process(snap(setpoint=350, power="Off", mode="off", fire="Off"))
    assert closed is not None and closed.aggregate_setpoint == 275
    with sessions() as session:
        stored = session.get(Cook, closed.id)
        assert stored is not None
        stored.setpoint_override = 300
        session.commit()
        assert stored.effective_setpoint == 300


def test_incomplete_cook_timeout(sessions: sessionmaker[Session], clock: FakeClock) -> None:
    service = CookService(sessions, clock, incomplete_timeout_minutes=90)
    service.process(snap(setpoint=275))
    clock.advance(hours=1)
    service.process(snap(setpoint=275, power="Fan", mode="off", fire="Cool Down"))
    clock.advance(minutes=90)
    closed = service.process(snap(setpoint=275, power="Fan", mode="off", fire="Cool Down"))
    assert closed is not None and closed.status == "closed" and closed.incomplete
    assert closed.cooldown_duration_seconds == int(timedelta(minutes=90).total_seconds())


def test_probe_done_uses_connected_probe_target(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    service = CookService(sessions, clock)
    cook = service.process(snap(setpoint=275, fire="Running"))
    assert cook is not None
    clock.advance(minutes=45)
    cook = service.process(
        snap(
            setpoint=275,
            fire="Running",
            probe1=203,
            probe1_connected=True,
            probe1_target=203,
            probe2=None,
            probe2_connected=False,
            probe2_target=165,
        )
    )
    assert cook is not None and cook.time_to_done_seconds == 2700
    clock.advance(seconds=10)
    service.process(
        snap(
            setpoint=275,
            fire="Running",
            probe1=205,
            probe1_connected=True,
            probe1_target=203,
            probe2=None,
            probe2_connected=False,
            probe2_target=165,
        )
    )
    assert kinds(sessions, cook.id).count("probe_done") == 1


def test_warning_sensor_change_records_warning(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    service = CookService(sessions, clock)
    cook = service.process(snap())
    assert cook is not None
    clock.advance(seconds=10)
    service.process(snap(warning="Low pellets"))
    clock.advance(seconds=10)
    service.process(snap(warning="Low pellets"))
    assert kinds(sessions, cook.id).count("warning") == 1


def test_garbage_snapshot_does_not_end_startup(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    service = CookService(sessions, clock)
    cook = service.process(snap())
    assert cook is not None
    clock.advance(seconds=10)

    cook = service.process(snap(setpoint=65535, mode="off", warning="Unknown"))

    assert cook is not None and cook.status == "startup"
    with sessions() as session:
        samples = list(session.scalars(select(Sample).where(Sample.cook_id == cook.id)))
    assert len(samples) == 1


def test_garbage_snapshot_does_not_start_cooldown(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    service = CookService(sessions, clock)
    cook = service.process(snap(setpoint=275, fire="Running"))
    assert cook is not None
    clock.advance(seconds=10)

    cook = service.process(snap(setpoint=65535, mode="off", warning="Unknown"))

    assert cook is not None and cook.status == "cook"


def test_repeated_valid_snapshot_records_each_change_once(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    service = CookService(sessions, clock)
    cook = service.process(snap(setpoint=275, fire="Running"))
    assert cook is not None

    changed = snap(
        setpoint=350,
        mode="fan_only",
        fire="Running",
        probe2=165,
        probe2_connected=True,
        warning="Low pellets",
    )
    for _ in range(6):
        service.process(changed)

    assert kinds(sessions, cook.id).count("probe_connected") == 1
    assert kinds(sessions, cook.id).count("setpoint_changed") == 1
    assert kinds(sessions, cook.id).count("mode_changed") == 1
    assert kinds(sessions, cook.id).count("warning") == 1


def test_valid_snapshot_after_invalid_streak_records_one_gap(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    service = CookService(sessions, clock)
    cook = service.process(snap(setpoint=275, fire="Running"))
    assert cook is not None
    clock.advance(seconds=2)
    service.process(snap(setpoint=65535, mode="off", warning="Unknown"))
    clock.advance(seconds=2)
    service.process(snap(setpoint=0, mode="off", warning="Unknown"))
    clock.advance(seconds=2)

    resumed = service.process(snap(setpoint=275, fire="Running"))

    assert resumed is not None and resumed.has_gap
    assert kinds(sessions, cook.id).count("data_gap") == 1
    with sessions() as session:
        samples = list(session.scalars(select(Sample).where(Sample.cook_id == cook.id)))
    assert len(samples) == 2
