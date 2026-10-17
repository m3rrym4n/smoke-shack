from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Cook, Event, Sample


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True)
class GrillSnapshot:
    pit_temp: float | None = None
    setpoint: float | None = None
    probe1: float | None = None
    probe2: float | None = None
    probe1_connected: bool = False
    probe2_connected: bool = False
    probe1_target: float | None = None
    probe2_target: float | None = None
    extra_probes: dict[str, float | None] = field(default_factory=dict)
    fire_state: str | None = None
    power_state: str | None = None
    hvac_mode: str | None = None
    warning: str | None = None


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC).replace(microsecond=0)


class CookService:
    def __init__(
        self,
        sessions: sessionmaker[Session],
        clock: Clock | None = None,
        sample_interval_seconds: int = 10,
        incomplete_timeout_minutes: int = 90,
    ) -> None:
        self.sessions = sessions
        self.clock = clock or SystemClock()
        self.sample_interval = timedelta(seconds=sample_interval_seconds)
        self.incomplete_timeout = timedelta(minutes=incomplete_timeout_minutes)

    def process(self, snapshot: GrillSnapshot, at: datetime | None = None) -> Cook | None:
        now = as_utc(at or self.clock.now()).replace(microsecond=0)
        with self.sessions() as session:
            cook = session.scalar(
                select(Cook).where(Cook.ended_at.is_(None)).order_by(Cook.started_at.desc())
            )
            if cook is None:
                if not self._is_ignition(snapshot):
                    return None
                cook = Cook(started_at=now, status="startup")
                session.add(cook)
                session.flush()
                self._event(session, cook, now, "fire_lit", "Fire lit")
                self._event(
                    session,
                    cook,
                    now,
                    "phase_changed",
                    "Startup started",
                    {"to": "startup"},
                )
                if snapshot.setpoint is not None and snapshot.setpoint != 150:
                    self._start_cook_phase(session, cook, now)
            previous = session.scalar(
                select(Sample).where(Sample.cook_id == cook.id).order_by(Sample.ts.desc()).limit(1)
            )
            self._record_changes(session, cook, previous, snapshot, now)
            if previous is None or now - as_utc(previous.ts) >= self.sample_interval:
                if previous is not None and now - as_utc(previous.ts) > self.sample_interval * 3:
                    cook.has_gap = True
                    self._event(
                        session,
                        cook,
                        now,
                        "data_gap",
                        "Home Assistant data gap",
                        {"start": _iso(as_utc(previous.ts)), "end": _iso(now)},
                    )
                session.add(self._sample(cook.id, snapshot, now))
            self._advance_phase(session, cook, snapshot, now)
            self._record_time_to_done(session, cook, snapshot, now)
            cook.updated_at = now
            session.commit()
            return cook

    def active_cook(self) -> Cook | None:
        with self.sessions() as session:
            return session.scalar(select(Cook).where(Cook.ended_at.is_(None)))

    @staticmethod
    def _is_ignition(snapshot: GrillSnapshot) -> bool:
        mode = _normalized(snapshot.hvac_mode)
        fire = _normalized(snapshot.fire_state)
        power = _normalized(snapshot.power_state)
        return mode == "heat" and (fire in {"startup", "running"} or power == "on")

    def _advance_phase(
        self, session: Session, cook: Cook, snapshot: GrillSnapshot, now: datetime
    ) -> None:
        mode = _normalized(snapshot.hvac_mode)
        fire = _normalized(snapshot.fire_state)
        power = _normalized(snapshot.power_state)
        if cook.status == "startup" and snapshot.setpoint is not None and snapshot.setpoint != 150:
            self._start_cook_phase(session, cook, now)
        if cook.status in {"startup", "cook"} and (mode == "off" or fire == "cool down"):
            if cook.startup_ended_at is None:
                cook.startup_ended_at = now
            cook.cook_ended_at = now
            cook.status = "cooldown"
            self._event(
                session, cook, now, "phase_changed", "Cool down started", {"to": "cooldown"}
            )
        if cook.status == "cooldown":
            if fire == "off" and power == "off":
                self._close(session, cook, now, incomplete=False)
            elif cook.cook_ended_at and now - as_utc(cook.cook_ended_at) >= self.incomplete_timeout:
                self._close(session, cook, now, incomplete=True)

    def _start_cook_phase(self, session: Session, cook: Cook, now: datetime) -> None:
        if cook.status != "startup":
            return
        cook.startup_ended_at = now
        cook.status = "cook"
        self._event(session, cook, now, "phase_changed", "Cook started", {"to": "cook"})

    def _close(self, session: Session, cook: Cook, now: datetime, incomplete: bool) -> None:
        cook.cooldown_ended_at = now
        cook.ended_at = now
        cook.status = "closed"
        cook.incomplete = incomplete
        cook.aggregate_setpoint = self._aggregate_setpoint(session, cook, now)
        self._event(
            session,
            cook,
            now,
            "phase_changed",
            "Cook closed",
            {"to": "closed", "incomplete": incomplete},
        )

    @staticmethod
    def _aggregate_setpoint(session: Session, cook: Cook, end: datetime) -> float | None:
        if cook.startup_ended_at is None:
            return None
        samples = list(
            session.scalars(
                select(Sample)
                .where(Sample.cook_id == cook.id, Sample.ts >= cook.startup_ended_at)
                .order_by(Sample.ts)
            )
        )
        totals: dict[float, float] = {}
        for index, sample in enumerate(samples):
            if sample.setpoint is None:
                continue
            next_ts = (
                samples[index + 1].ts if index + 1 < len(samples) else (cook.cook_ended_at or end)
            )
            seconds = max(0.0, (as_utc(next_ts) - as_utc(sample.ts)).total_seconds())
            totals[sample.setpoint] = totals.get(sample.setpoint, 0.0) + seconds
        return max(totals, key=lambda setpoint: totals[setpoint]) if totals else None

    def _record_changes(
        self,
        session: Session,
        cook: Cook,
        previous: Sample | None,
        current: GrillSnapshot,
        now: datetime,
    ) -> None:
        if previous is None:
            if _normalized(current.fire_state) == "fail":
                self._event(session, cook, now, "warning", "Grill fire state failed")
            self._record_warning_change(session, cook, current.warning, now)
            return
        changes = (
            ("setpoint_changed", previous.setpoint, current.setpoint, "Setpoint changed"),
            ("mode_changed", previous.hvac_mode, current.hvac_mode, "Mode changed"),
        )
        for kind, old, new, title in changes:
            if old != new:
                self._event(session, cook, now, kind, title, {"from": old, "to": new})
        for name, old, new in (
            ("probe1", previous.probe1, current.probe1),
            ("probe2", previous.probe2, current.probe2),
        ):
            if (old is None) != (new is None):
                state = "connected" if new is not None else "disconnected"
                self._event(
                    session,
                    cook,
                    now,
                    f"probe_{state}",
                    f"{name} {state}",
                    {"probe": name},
                )
        if _normalized(previous.fire_state) != "fail" and _normalized(current.fire_state) == "fail":
            self._event(session, cook, now, "warning", "Grill fire state failed")
        self._record_warning_change(session, cook, current.warning, now)

    def _record_warning_change(
        self, session: Session, cook: Cook, warning: str | None, now: datetime
    ) -> None:
        value = None if warning is None or warning.casefold() == "none" else warning
        warning_events = session.scalars(
            select(Event)
            .where(Event.cook_id == cook.id, Event.kind.in_(("warning", "warning_cleared")))
            .order_by(Event.id.desc())
        )
        latest = next((event for event in warning_events if "warning" in event.data), None)
        previous = latest.data.get("warning") if latest is not None else None
        if value == previous:
            return
        if value is None:
            if latest is not None and "warning" in latest.data:
                self._event(
                    session,
                    cook,
                    now,
                    "warning_cleared",
                    "Grill warning cleared",
                    {"warning": None},
                )
            return
        self._event(session, cook, now, "warning", "Grill warning", {"warning": value})

    def _record_time_to_done(
        self, session: Session, cook: Cook, snapshot: GrillSnapshot, now: datetime
    ) -> None:
        if cook.startup_ended_at is None or cook.cook_ended_at is not None:
            return
        done_probes = list(
            session.scalars(
                select(Event.data).where(Event.cook_id == cook.id, Event.kind == "probe_done")
            )
        )
        for probe, reading, target, connected in (
            (1, snapshot.probe1, snapshot.probe1_target, snapshot.probe1_connected),
            (2, snapshot.probe2, snapshot.probe2_target, snapshot.probe2_connected),
        ):
            if (
                probe not in {data.get("probe") for data in done_probes}
                and connected
                and reading is not None
                and target is not None
                and reading >= target
            ):
                if cook.time_to_done_seconds is None:
                    cook.time_to_done_seconds = int(
                        (now - as_utc(cook.startup_ended_at)).total_seconds()
                    )
                self._event(
                    session,
                    cook,
                    now,
                    "probe_done",
                    "Probe reached target",
                    {"probe": probe, "target": target},
                )

    @staticmethod
    def _sample(cook_id: int, snapshot: GrillSnapshot, now: datetime) -> Sample:
        return Sample(
            cook_id=cook_id,
            ts=now,
            pit_temp=snapshot.pit_temp,
            setpoint=snapshot.setpoint,
            probe1=snapshot.probe1,
            probe2=snapshot.probe2,
            probe1_target=snapshot.probe1_target,
            probe2_target=snapshot.probe2_target,
            extra_probes=snapshot.extra_probes,
            fire_state=snapshot.fire_state,
            power_state=snapshot.power_state,
            hvac_mode=snapshot.hvac_mode,
        )

    @staticmethod
    def _event(
        session: Session,
        cook: Cook,
        ts: datetime,
        kind: str,
        title: str,
        data: dict[str, object] | None = None,
    ) -> None:
        session.add(
            Event(cook_id=cook.id, ts=ts, kind=kind, source="auto", title=title, data=data or {})
        )


def _iso(value: datetime) -> str:
    return as_utc(value).isoformat().replace("+00:00", "Z")


def _normalized(value: str | None) -> str:
    return (value or "").casefold().replace("_", " ")
