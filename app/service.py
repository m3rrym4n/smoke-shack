from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.equipment import first_equipment_id
from app.models import Channel, ChannelReading, Cook, Event, Sample

logger = logging.getLogger(__name__)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True)
class GrillSnapshot:
    grill_name: str | None = None
    pit_temp: float | None = None
    setpoint: float | None = None
    probe1: float | None = None
    probe2: float | None = None
    probe1_connected: bool = False
    probe2_connected: bool = False
    probe1_target: float | None = None
    probe2_target: float | None = None
    extra_probes: dict[str, float | None] = field(default_factory=dict)
    extra_probe_targets: dict[str, float | None] = field(default_factory=dict)
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
        if 2 <= len(missing) < len(core):
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
        data_gap_event_min_seconds: int = 120,
    ) -> None:
        self.sessions = sessions
        self.clock = clock or SystemClock()
        self.sample_interval = timedelta(seconds=sample_interval_seconds)
        self.incomplete_timeout = timedelta(minutes=incomplete_timeout_minutes)
        self.data_gap_event_min_seconds = data_gap_event_min_seconds
        self._invalid_since: datetime | None = None
        self._previous_snapshots: dict[int, GrillSnapshot] = {}

    def process(self, snapshot: GrillSnapshot, at: datetime | None = None) -> Cook | None:
        now = as_utc(at or self.clock.now()).replace(microsecond=0)
        with self.sessions() as session:
            cook = session.scalar(
                select(Cook)
                .where(Cook.ended_at.is_(None), Cook.status != "planned")
                .order_by(Cook.started_at.desc())
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
                cook = self._adopt_planned(session, now)
                if cook is None:
                    cook = Cook(
                        started_at=now,
                        status="startup",
                        equipment_id=first_equipment_id(session),
                    )
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
                gap_seconds = int((now - as_utc(previous.ts)).total_seconds())
                if gap_seconds >= self.data_gap_event_min_seconds:
                    self._event(
                        session,
                        cook,
                        now,
                        "data_gap",
                        "Home Assistant data gap",
                        {"start": _iso(as_utc(previous.ts)), "end": _iso(now)},
                    )
                else:
                    self._record_brief_gap_summary(session, cook, now, gap_seconds)
            if (
                previous is None
                or resumed_after_invalid
                or now - as_utc(previous.ts) >= self.sample_interval
            ):
                if gap_detected:
                    logger.info("cook %s Home Assistant data gap ended", cook.id)
                session.add(self._sample(session, cook, snapshot, now))
            self._advance_phase(session, cook, previous, snapshot, now)
            self._record_time_to_done(session, cook, snapshot, now)
            self._previous_snapshots[cook.id] = snapshot
            cook.updated_at = now
            session.commit()
            return cook

    def active_cook(self) -> Cook | None:
        with self.sessions() as session:
            return session.scalar(
                select(Cook).where(Cook.ended_at.is_(None), Cook.status != "planned")
            )

    @staticmethod
    def _adopt_planned(session: Session, now: datetime) -> Cook | None:
        """Claim the oldest plan with a conditional update in the startup transaction."""
        while True:
            planned_id = session.scalar(
                select(Cook.id)
                .where(Cook.status == "planned")
                .order_by(Cook.created_at, Cook.id)
                .limit(1)
            )
            if planned_id is None:
                return None
            claimed = session.execute(
                update(Cook)
                .where(Cook.id == planned_id, Cook.status == "planned")
                .values(status="startup", started_at=now, updated_at=now)
            )
            if claimed.rowcount == 1:
                return session.get(Cook, planned_id)
            session.expire_all()

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
        if previous.setpoint != current.setpoint:
            new_setpoint = _temperature_text(current.setpoint)
            title = (
                f"Setpoint changed to {new_setpoint}°F"
                if new_setpoint is not None
                else "Setpoint changed"
            )
            old_setpoint = _temperature_text(previous.setpoint)
            description = f"from {old_setpoint}°F" if old_setpoint is not None else None
            self._event(
                session,
                cook,
                now,
                "setpoint_changed",
                title,
                {"from": previous.setpoint, "to": current.setpoint},
                description,
            )
        if previous.hvac_mode != current.hvac_mode:
            self._event(
                session,
                cook,
                now,
                "mode_changed",
                "Mode changed",
                {"from": previous.hvac_mode, "to": current.hvac_mode},
            )
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
                and target > 0
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

    def _record_brief_gap_summary(
        self, session: Session, cook: Cook, started_at: datetime, gap_seconds: int
    ) -> None:
        summary = session.scalar(
            select(Event).where(
                Event.cook_id == cook.id, Event.kind == "data_gap_summary"
            )
        )
        if summary is None:
            summary = Event(
                cook_id=cook.id,
                ts=started_at,
                kind="data_gap_summary",
                source="auto",
                title="Brief Home Assistant data gaps",
                data={"count": 0, "total_seconds": 0, "longest_seconds": 0},
            )
            session.add(summary)
        count = int(summary.data.get("count", 0)) + 1
        total = int(summary.data.get("total_seconds", 0)) + gap_seconds
        longest = max(int(summary.data.get("longest_seconds", 0)), gap_seconds)
        summary.data = {"count": count, "total_seconds": total, "longest_seconds": longest}
        summary.description = (
            f"{count} brief {'gap' if count == 1 else 'gaps'}, "
            f"{_duration_text(total)} total, longest {longest}s"
        )

    @staticmethod
    def _sample(
        session: Session, cook: Cook, snapshot: GrillSnapshot, now: datetime
    ) -> Sample:
        sample = Sample(
            cook_id=cook.id,
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
        values = {
            "pit": (snapshot.pit_temp, snapshot.setpoint),
            "probe1": (snapshot.probe1, snapshot.probe1_target),
            "probe2": (snapshot.probe2, snapshot.probe2_target),
        }
        extra_keys = snapshot.extra_probes.keys() | snapshot.extra_probe_targets.keys()
        values.update(
            {
                raw_key.rsplit(".", 1)[-1]: (
                    snapshot.extra_probes.get(raw_key),
                    snapshot.extra_probe_targets.get(raw_key),
                )
                for raw_key in extra_keys
            }
        )
        channels = {
            channel.key: channel
            for channel in session.scalars(
                select(Channel).where(Channel.equipment_id == cook.equipment_id)
            )
        }
        for key, (value, target) in values.items():
            if value is None and target is None:
                continue
            channel = channels.get(key)
            if channel is None:
                logger.debug("ignoring snapshot channel %s with no matching equipment channel", key)
                continue
            sample.channel_readings.append(
                ChannelReading(channel_id=channel.id, value=value, target=target)
            )
        return sample

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
        description: str | None = None,
    ) -> None:
        session.add(
            Event(
                cook_id=cook.id,
                ts=ts,
                kind=kind,
                source="auto",
                title=title,
                description=description,
                data=data or {},
            )
        )


def _iso(value: datetime) -> str:
    return as_utc(value).isoformat().replace("+00:00", "Z")


def _normalized(value: str | None) -> str:
    return (value or "").casefold().replace("_", " ")


def _duration_text(seconds: int) -> str:
    minutes, remaining = divmod(seconds, 60)
    if minutes and remaining:
        return f"{minutes}m {remaining}s"
    if minutes:
        return f"{minutes}m"
    return f"{remaining}s"


def _temperature_text(value: float | None) -> str | None:
    return str(round(value)) if value is not None else None
