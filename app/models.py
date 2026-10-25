from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.database import Base

cook_spices = Table(
    "cook_spices",
    Base.metadata,
    Column("cook_id", ForeignKey("cooks.id", ondelete="CASCADE"), primary_key=True),
    Column("spice_id", ForeignKey("spices.id"), primary_key=True),
)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


class UTCDateTime(TypeDecorator[datetime]):
    """Persist an aware UTC datetime as an ISO 8601 string, including on SQLite."""

    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: object) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def process_result_value(self, value: str | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


class Cook(Base):
    __tablename__ = "cooks"
    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    startup_ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    cook_ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    cooldown_ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    status: Mapped[str] = mapped_column(String(20), default="startup")
    meat_id: Mapped[int | None] = mapped_column(ForeignKey("meat.id"))
    pellet_id: Mapped[int | None] = mapped_column(ForeignKey("pellets.id"))
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id"))
    rotisserie: Mapped[bool] = mapped_column(Boolean, default=False)
    seasonings: Mapped[str | None] = mapped_column(Text)
    sauces: Mapped[str | None] = mapped_column(Text)
    prep_time_minutes: Mapped[int | None]
    results_text: Mapped[str | None] = mapped_column(Text)
    aggregate_setpoint: Mapped[float | None]
    setpoint_override: Mapped[float | None]
    time_to_done_seconds: Mapped[int | None]
    has_gap: Mapped[bool] = mapped_column(Boolean, default=False)
    incomplete: Mapped[bool] = mapped_column(Boolean, default=False)
    pellets_used_lb: Mapped[float | None]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)
    samples: Mapped[list[Sample]] = relationship(
        back_populates="cook", cascade="all, delete-orphan"
    )
    events: Mapped[list[Event]] = relationship(back_populates="cook", cascade="all, delete-orphan")
    spices: Mapped[list[Spice]] = relationship(
        secondary=cook_spices,
        order_by="Spice.name",
    )

    @property
    def startup_duration_seconds(self) -> int | None:
        return _duration(self.started_at, self.startup_ended_at)

    @property
    def cook_duration_seconds(self) -> int | None:
        return _duration(self.startup_ended_at, self.cook_ended_at)

    @property
    def cooldown_duration_seconds(self) -> int | None:
        return _duration(self.cook_ended_at, self.cooldown_ended_at)

    @property
    def grill_duration_seconds(self) -> int | None:
        return _duration(self.started_at, self.ended_at)

    @property
    def effective_setpoint(self) -> float | None:
        if self.setpoint_override is not None:
            return self.setpoint_override
        return self.aggregate_setpoint


def _duration(start: datetime | None, end: datetime | None) -> int | None:
    return int((end - start).total_seconds()) if start is not None and end is not None else None


class Sample(Base):
    __tablename__ = "samples"
    __table_args__ = (Index("ix_samples_cook_ts", "cook_id", "ts"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    cook_id: Mapped[int] = mapped_column(ForeignKey("cooks.id"))
    ts: Mapped[datetime] = mapped_column(UTCDateTime())
    pit_temp: Mapped[float | None]
    setpoint: Mapped[float | None]
    probe1: Mapped[float | None]
    probe2: Mapped[float | None]
    probe1_target: Mapped[float | None]
    probe2_target: Mapped[float | None]
    extra_probes: Mapped[dict[str, float | None]] = mapped_column(JSON, default=dict)
    fire_state: Mapped[str | None]
    power_state: Mapped[str | None]
    hvac_mode: Mapped[str | None]
    cook: Mapped[Cook] = relationship(back_populates="samples")


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    cook_id: Mapped[int] = mapped_column(ForeignKey("cooks.id"))
    ts: Mapped[datetime] = mapped_column(UTCDateTime())
    kind: Mapped[str] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(10), default="auto")
    title: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    photo_path: Mapped[str | None]
    cook: Mapped[Cook] = relationship(back_populates="events")


class Photo(Base):
    __tablename__ = "photos"
    id: Mapped[int] = mapped_column(primary_key=True)
    cook_id: Mapped[int] = mapped_column(ForeignKey("cooks.id"))
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"))
    path: Mapped[str]
    caption: Mapped[str | None]


class Meat(Base):
    __tablename__ = "meat"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str]
    pounds: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    price_per_pound: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    store: Mapped[str | None]
    purchased_on: Mapped[date] = mapped_column(Date)
    photo_path: Mapped[str | None]
    cooked: Mapped[bool] = mapped_column(Boolean, default=False)

    @property
    def has_photo(self) -> bool:
        return self.photo_path is not None

    @property
    def photo_url(self) -> str | None:
        return _pantry_photo_url("meat", self.id, self.photo_path)


class Pellet(Base):
    __tablename__ = "pellets"
    id: Mapped[int] = mapped_column(primary_key=True)
    vendor: Mapped[str]
    product_name: Mapped[str]
    price_per_pound: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    purchased_on: Mapped[date] = mapped_column(Date)
    photo_path: Mapped[str | None]

    @property
    def has_photo(self) -> bool:
        return self.photo_path is not None

    @property
    def photo_url(self) -> str | None:
        return _pantry_photo_url("pellets", self.id, self.photo_path)


class Spice(Base):
    __tablename__ = "spices"
    id: Mapped[int] = mapped_column(primary_key=True)
    brand: Mapped[str]
    name: Mapped[str]
    price: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    size_oz: Mapped[Decimal | None] = mapped_column(Numeric(6, 1))
    notes: Mapped[str | None] = mapped_column(Text)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)
    photo_path: Mapped[str | None]

    @property
    def has_photo(self) -> bool:
        return self.photo_path is not None

    @property
    def photo_url(self) -> str | None:
        return _pantry_photo_url("spices", self.id, self.photo_path)


def _pantry_photo_url(kind: str, item_id: int, photo_path: str | None) -> str | None:
    if photo_path is None:
        return None
    try:
        version = Path(photo_path).stat().st_mtime_ns
    except OSError:
        version = 0
    return f"/api/{kind}/{item_id}/photo?v={version}"


Index(
    "uq_spices_brand_name_ci",
    func.lower(Spice.brand),
    func.lower(Spice.name),
    unique=True,
)


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    keep_warm: Mapped[bool] = mapped_column(Boolean, default=False)
    keep_warm_temp: Mapped[float | None]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)


class ProfileStep(Base):
    __tablename__ = "profile_steps"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    position: Mapped[int]
    grill_temp: Mapped[float]
    stop_mode: Mapped[str]
    duration_minutes: Mapped[int | None]
    probe: Mapped[int | None]
    target_temp: Mapped[float | None]
    instructions: Mapped[str] = mapped_column(Text, default="")


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    body: Mapped[str] = mapped_column(Text)
    title: Mapped[str]
    scope: Mapped[str]
    cook_id: Mapped[int | None] = mapped_column(ForeignKey("cooks.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
