from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Cook, Event, Sample

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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

    def implausible_reason(self) -> str | None:
        if self.setpoint is not None and not 100 <= self.setpoint <= 550:
            return f"setpoint {self.setpoint} is outside 100-550"
        for name, value in (
            ("pit temperature", self.pit_temp),
            ("probe 1 temperature", self.probe1),
            ("probe 2 temperature", self.probe2),
            *(
                (f"extra probe {name} temperature", value)
                for name, value in self.extra_probes.items()
            ),
        ):
            if value is not None and (value > 600 or value == 65535):
                return f"{name} {value} is invalid"
        if _normalized(self.warning) == "unknown":
            return "warning is unknown"
        core = {
            "climate": self.hvac_mode,
            "fire_state": self.fire_state,
            "power_state": self.power_state,
        }
        missing = [
            name
            for name, value in core.items()
            if value is None or _normalized(value) in {"unknown", "unavailable"}
        ]
        if missing and len(missing) != len(core):
            return f"core entity {missing[0]} is unavailable while others are present"
        return None

    def is_plausible(self) -> bool:
        return self.implausible_reason() is None


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
        self._invalid_since: datetime | None = None
        self._previous_snapshots: dict[int, GrillSnapshot] = {}

    def process(self, snapshot: GrillSnapshot, at: datetime | None = None) -> Cook | None:
        now = as_utc(at or self.clock.now()).replace(microsecond=0)
        with self.sessions() as session:
            cook = session.scalar(
                select(Cook).where(Cook.ended_at.is_(None)).order_by(Cook.started_at.desc())
            )
            reason = snapshot.implausible_reason()
            if reason is not None:
                if self._invalid_since is None:
                    self._invalid_since = now
                    logger.info("ignoring implausible snapshot: %s", reason)
                return cook
            resumed_after_invalid = self._invalid_since is not None
            self._invalid_since = None
            if cook is not None and cook.status == "cooldown" and self._is_ignition(snapshot):
                self._close(session, cook, now, incomplete=True)
                cook = None
            if cook is None:
                if not self._is_ignition(snapshot):
                    return None
                cook = Cook(started_at=now, status="startup")
                session.add(cook)
                session.flush()
                logger.info("cook %s started", cook.id)
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
            previous_snapshot = self._previous_snapshots.get(cook.id)
            if previous_snapshot is None and previous is not None:
                previous_snapshot = self._snapshot_from_sample(previous)
            self._record_changes(session, cook, previous_snapshot, snapshot, now)
            gap_detected = previous is not None and (
                resumed_after_invalid or now - as_utc(previous.ts) > self.sample_interval * 3
            )
            if gap_detected and previous is not None:
                cook.has_gap = True
                self._event(
                    session,
                    cook,
                    now,
                    "data_gap",
                    "Home Assistant data gap",
                    {"start": _iso(as_utc(previous.ts)), "end": _iso(now)},
                )
            if (
                previous is None
                or resumed_after_invalid
                or now - as_utc(previous.ts) >= self.sample_interval
            ):
                if gap_detected:
                    logger.info("cook %s Home Assistant data gap ended", cook.id)
                session.add(self._sample(cook.id, snapshot, now))
            self._advance_phase(session, cook, previous, snapshot, now)
            self._record_time_to_done(session, cook, snapshot, now)
            self._previous_snapshots[cook.id] = snapshot
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
        return mode == "heat" and fire in {"startup", "running"}

    def _advance_phase(
        self,
        session: Session,
        cook: Cook,
        previous: Sample | None,
        snapshot: GrillSnapshot,
        now: datetime,
    ) -> None:
        mode = _normalized(snapshot.hvac_mode)
        fire = _normalized(snapshot.fire_state)
        power = _normalized(snapshot.power_state)
        if cook.status == "startup" and snapshot.setpoint is not None and snapshot.setpoint != 150:
            self._start_cook_phase(session, cook, now)
        previous_fire = _normalized(previous.fire_state) if previous is not None else None
        cooldown_started = mode == "off" or (fire == "cool down" and previous_fire == "cool down")
        if cook.status in {"startup", "cook"} and cooldown_started:
            old_status = cook.status
            if cook.startup_ended_at is None:
                cook.startup_ended_at = now
            cook.cook_ended_at = now
            cook.status = "cooldown"
            logger.info("cook %s phase %s -> cooldown", cook.id, old_status)
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
        logger.info("cook %s phase startup -> cook", cook.id)
        self._event(session, cook, now, "phase_changed", "Cook started", {"to": "cook"})

    def _close(self, session: Session, cook: Cook, now: datetime, incomplete: bool) -> None:
        cook.cooldown_ended_at = now
        cook.ended_at = now
        cook.status = "closed"
        cook.incomplete = incomplete
        cook.aggregate_setpoint = self._aggregate_setpoint(session, cook, now)
        logger.info("cook %s phase cooldown -> closed", cook.id)
        logger.info("cook %s closed: %s", cook.id, "incomplete" if incomplete else "complete")
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
        previous: GrillSnapshot | None,
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
            ("probe1", previous.probe1_connected, current.probe1_connected),
            ("probe2", previous.probe2_connected, current.probe2_connected),
        ):
            if old != new:
                state = "connected" if new else "disconnected"
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
    def _snapshot_from_sample(sample: Sample) -> GrillSnapshot:
        return GrillSnapshot(
            pit_temp=sample.pit_temp,
            setpoint=sample.setpoint,
            probe1=sample.probe1,
            probe2=sample.probe2,
            probe1_connected=sample.probe1 is not None,
            probe2_connected=sample.probe2 is not None,
            probe1_target=sample.probe1_target,
            probe2_target=sample.probe2_target,
            extra_probes=sample.extra_probes,
            fire_state=sample.fire_state,
            power_state=sample.power_state,
            hvac_mode=sample.hvac_mode,
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
