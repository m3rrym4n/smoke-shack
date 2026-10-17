from __future__ import annotations

from datetime import timedelta

from conftest import FakeClock, FakeHAClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Cook, Event, Sample
from app.service import CookService, GrillSnapshot


def snap(
    *, setpoint: float = 150, power: str = "on", mode: str = "heat", probe1: float | None = None
) -> GrillSnapshot:
    return GrillSnapshot(
        pit_temp=100,
        setpoint=setpoint,
        probe1=probe1,
        fire_state="on",
        power_state=power,
        hvac_mode=mode,
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
    service.process(snap(setpoint=275))
    clock.advance(hours=2)
    service.process(snap(setpoint=275, power="off", mode="fan_only"))
    clock.advance(minutes=10)
    closed = service.process(snap(setpoint=275, power="off", mode="off"))
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
    assert service.process(snap(power="on", mode="fan_only")) is None
    cook = service.process(snap(setpoint=275))
    assert cook is not None
    clock.advance(seconds=10)
    cook = service.process(snap(setpoint=275, mode="fan_only"))
    assert cook is not None and cook.status == "cook"
    assert "mode_changed" in kinds(sessions, cook.id)


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
    service.process(snap(setpoint=350, power="off", mode="fan_only"))
    clock.advance(minutes=5)
    closed = service.process(snap(setpoint=350, power="off", mode="off"))
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
    service.process(snap(setpoint=275, power="off", mode="fan_only"))
    clock.advance(minutes=90)
    closed = service.process(snap(setpoint=275, power="off", mode="fan_only"))
    assert closed is not None and closed.status == "closed" and closed.incomplete
    assert closed.cooldown_duration_seconds == int(timedelta(minutes=90).total_seconds())
