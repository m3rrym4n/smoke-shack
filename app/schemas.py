from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

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
