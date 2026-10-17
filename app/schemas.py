from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class MeatCreate(BaseModel):
    type: NonEmptyStr
    pounds: float = Field(gt=0)
    price_per_pound: float = Field(ge=0)
    store: str | None = None
    purchased_on: date = Field(default_factory=date.today)


class MeatUpdate(BaseModel):
    type: NonEmptyStr | None = None
    pounds: float | None = Field(default=None, gt=0)
    price_per_pound: float | None = Field(default=None, ge=0)
    store: str | None = None
    purchased_on: date | None = None


class MeatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    pounds: float
    price_per_pound: float
    store: str | None
    purchased_on: date


class PelletCreate(BaseModel):
    vendor: NonEmptyStr
    product_name: NonEmptyStr
    price_per_pound: float = Field(ge=0)
    purchased_on: date = Field(default_factory=date.today)


class PelletUpdate(BaseModel):
    vendor: NonEmptyStr | None = None
    product_name: NonEmptyStr | None = None
    price_per_pound: float | None = Field(default=None, ge=0)
    purchased_on: date | None = None


class PelletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vendor: str
    product_name: str
    price_per_pound: float
    purchased_on: date


NoteScope = Literal["this_cook", "pellets", "gear"]


class NoteCreate(BaseModel):
    title: NonEmptyStr
    body: NonEmptyStr
    scope: NoteScope
    cook_id: int | None = None


class NoteUpdate(BaseModel):
    title: NonEmptyStr | None = None
    body: NonEmptyStr | None = None
    scope: NoteScope | None = None
    cook_id: int | None = None

    @field_validator("title", "body", "scope", mode="before")
    @classmethod
    def required_fields_cannot_be_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("field cannot be null")
        return value


class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str
    scope: NoteScope
    cook_id: int | None
    created_at: datetime


def _utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value.astimezone(UTC).replace(microsecond=0)


class UserEventCreate(BaseModel):
    title: NonEmptyStr
    description: str | None = None
    ts: datetime | None = None

    _validate_ts = field_validator("ts")(_utc_datetime)


class UserEventUpdate(BaseModel):
    title: NonEmptyStr | None = None
    description: str | None = None
    ts: datetime | None = None

    _validate_ts = field_validator("ts")(_utc_datetime)

    @field_validator("title", "ts", mode="before")
    @classmethod
    def required_fields_cannot_be_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("field cannot be null")
        return value


class EventResponse(BaseModel):
    id: int
    ts: datetime
    elapsed_seconds: int
    kind: str
    source: str
    title: str
    description: str | None
    data: dict[str, object]
    photo_path: str | None
