from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

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


class SpiceCreate(BaseModel):
    brand: NonEmptyStr
    name: NonEmptyStr
    price: float | None = Field(default=None, ge=0)
    size_oz: float | None = Field(default=None, gt=0)
    notes: str | None = None


class SpiceUpdate(BaseModel):
    brand: NonEmptyStr | None = None
    name: NonEmptyStr | None = None
    price: float | None = Field(default=None, ge=0)
    size_oz: float | None = Field(default=None, gt=0)
    notes: str | None = None

    @field_validator("brand", "name", mode="before")
    @classmethod
    def required_fields_cannot_be_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("field cannot be null")
        return value


class SpiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    brand: str
    name: str
    price: float | None
    size_oz: float | None
    notes: str | None
    is_custom: bool
    created_at: datetime
    updated_at: datetime


class CookUpdate(BaseModel):
    meat_id: int | None = None
    pellet_id: int | None = None
    profile_id: int | None = None
    rotisserie: bool | None = None
    seasonings: str | None = None
    sauces: str | None = None
    prep_time_minutes: int | None = Field(default=None, ge=0)
    results_text: str | None = None
    setpoint_override: float | None = None
    pellets_used_lb: float | None = Field(default=None, ge=0)
    spice_ids: list[int] = Field(default_factory=list)

    @field_validator("rotisserie", mode="before")
    @classmethod
    def rotisserie_cannot_be_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("field cannot be null")
        return value


class PlannedCookCreate(BaseModel):
    state: Literal["planned"]
    meat_id: int | None = None
    pellet_id: int | None = None
    profile_id: int | None = None
    rotisserie: bool = False
    seasonings: str | None = None
    sauces: str | None = None
    prep_time_minutes: int | None = Field(default=None, ge=0)
    results_text: str | None = None
    setpoint_override: float | None = None
    pellets_used_lb: float | None = Field(default=None, ge=0)
    spice_ids: list[int] = Field(default_factory=list)


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


UserEventKind = Literal["stall", "wrapped", "spritzed", "sauced", "flipped", "rested", "custom"]


class UserEventCreate(BaseModel):
    kind: UserEventKind = "custom"
    title: NonEmptyStr
    description: str | None = None
    ts: datetime | None = None

    _validate_ts = field_validator("ts")(_utc_datetime)


class UserEventUpdate(BaseModel):
    kind: UserEventKind | None = None
    title: NonEmptyStr | None = None
    description: str | None = None
    ts: datetime | None = None

    _validate_ts = field_validator("ts")(_utc_datetime)

    @field_validator("kind", "title", "ts", mode="before")
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


class PhotoUpdate(BaseModel):
    caption: str | None = None


class PhotoResponse(BaseModel):
    id: int
    cook_id: int
    event_id: int | None
    caption: str | None
    url: str


StopMode = Literal["time", "internal_temp"]


class ProfileStepInput(BaseModel):
    grill_temp: float = Field(ge=150, le=500)
    stop_mode: StopMode
    duration_minutes: int | None = Field(default=None, gt=0)
    probe: Literal[1, 2] | None = None
    target_temp: float | None = None
    instructions: str = ""

    @model_validator(mode="after")
    def validate_stop_condition(self) -> ProfileStepInput:
        if self.stop_mode == "time":
            if self.duration_minutes is None:
                raise ValueError("duration_minutes is required for time stop")
            if self.probe is not None or self.target_temp is not None:
                raise ValueError("probe and target_temp must be null for time stop")
        else:
            if self.probe is None or self.target_temp is None:
                raise ValueError("probe and target_temp are required for internal_temp stop")
            if self.duration_minutes is not None:
                raise ValueError("duration_minutes must be null for internal_temp stop")
        return self


class ProfileCreate(BaseModel):
    name: NonEmptyStr
    keep_warm: bool = False
    keep_warm_temp: float | None = None
    steps: list[ProfileStepInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_keep_warm(self) -> ProfileCreate:
        if self.keep_warm and self.keep_warm_temp is None:
            raise ValueError("keep_warm_temp is required when keep_warm is true")
        if not self.keep_warm and self.keep_warm_temp is not None:
            raise ValueError("keep_warm_temp must be null when keep_warm is false")
        return self


class ProfileUpdate(BaseModel):
    name: NonEmptyStr | None = None
    keep_warm: bool | None = None
    keep_warm_temp: float | None = None

    @field_validator("name", "keep_warm", mode="before")
    @classmethod
    def required_fields_cannot_be_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("field cannot be null")
        return value


class ProfileStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    grill_temp: float
    stop_mode: StopMode
    duration_minutes: int | None
    probe: int | None
    target_temp: float | None
    instructions: str


class ProfileListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    keep_warm: bool
    keep_warm_temp: float | None
    step_count: int
    created_at: datetime
    updated_at: datetime


class ProfileResponse(BaseModel):
    id: int
    name: str
    keep_warm: bool
    keep_warm_temp: float | None
    steps: list[ProfileStepResponse]
    created_at: datetime
    updated_at: datetime
