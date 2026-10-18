from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_session
from app.models import Cook, Meat, Pellet

router = APIRouter(prefix="/api/stats", tags=["stats"])
SessionDep = Annotated[Session, Depends(get_session)]
PACIFIC = ZoneInfo("America/Los_Angeles")


def _utc_boundary(value: date) -> datetime:
    return datetime.combine(value, time.min, PACIFIC).astimezone(UTC)


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z") if value else None


def _summary(values: list[int | None]) -> dict[str, int | None]:
    present = [value for value in values if value is not None]
    if not present:
        return {"avg": None, "min": None, "max": None}
    return {
        "avg": int(sum(present) / len(present) + 0.5),
        "min": min(present),
        "max": max(present),
    }


@router.get("/cooks")
def cook_stats(
    session: SessionDep,
    meat_type: str | None = None,
    pounds_min: float | None = Query(default=None, ge=0),
    pounds_max: float | None = Query(default=None, ge=0),
    setpoint: float | None = None,
    setpoint_tolerance: float = Query(default=10, ge=0),
    rotisserie: bool | None = None,
    pellet_id: int | None = None,
    pellet_vendor: str | None = None,
    pellet_product: str | None = None,
    since: date | None = None,
    until: date | None = None,
    include_incomplete: bool = False,
    exclude_gaps: bool = False,
) -> dict[str, Any]:
    query = select(Cook, Meat).join(Meat, Cook.meat_id == Meat.id).where(
        Cook.ended_at.is_not(None), Cook.status != "planned"
    )
    if meat_type is not None:
        query = query.where(func.lower(Meat.type).contains(meat_type.lower(), autoescape=True))
    if pounds_min is not None:
        query = query.where(Meat.pounds >= Decimal(str(pounds_min)))
    if pounds_max is not None:
        query = query.where(Meat.pounds <= Decimal(str(pounds_max)))
    if setpoint is not None:
        effective_setpoint = func.coalesce(Cook.setpoint_override, Cook.aggregate_setpoint)
        query = query.where(
            effective_setpoint >= setpoint - setpoint_tolerance,
            effective_setpoint <= setpoint + setpoint_tolerance,
        )
    if rotisserie is not None:
        query = query.where(Cook.rotisserie == rotisserie)
    if pellet_id is not None:
        query = query.where(Cook.pellet_id == pellet_id)
    if pellet_vendor is not None or pellet_product is not None:
        query = query.join(Pellet, Cook.pellet_id == Pellet.id)
        if pellet_vendor is not None:
            query = query.where(
                func.lower(Pellet.vendor).contains(pellet_vendor.lower(), autoescape=True)
            )
        if pellet_product is not None:
            query = query.where(
                func.lower(Pellet.product_name).contains(pellet_product.lower(), autoescape=True)
            )
    if since is not None:
        query = query.where(Cook.started_at >= _utc_boundary(since))
    if until is not None:
        query = query.where(Cook.started_at < _utc_boundary(until + timedelta(days=1)))
    if not include_incomplete:
        query = query.where(Cook.incomplete.is_(False))
    if exclude_gaps:
        query = query.where(Cook.has_gap.is_(False))

    rows = list(session.execute(query.order_by(Cook.started_at.desc())).tuples())
    cooks = [cook for cook, _meat in rows]

    return {
        "count": len(rows),
        "cook_seconds": _summary([cook.cook_duration_seconds for cook in cooks]),
        "grill_seconds": _summary([cook.grill_duration_seconds for cook in cooks]),
        "startup_seconds": _summary([cook.startup_duration_seconds for cook in cooks]),
        "cooldown_seconds": _summary([cook.cooldown_duration_seconds for cook in cooks]),
        "time_to_done_seconds": _summary([cook.time_to_done_seconds for cook in cooks]),
        "cooks": [
            {
                "id": cook.id,
                "started_at": _iso(cook.started_at),
                "meat_type": meat.type,
                "pounds": float(meat.pounds),
                "setpoint": cook.effective_setpoint,
                "cook_seconds": cook.cook_duration_seconds,
                "grill_seconds": cook.grill_duration_seconds,
                "time_to_done_seconds": cook.time_to_done_seconds,
            }
            for cook, meat in rows[:200]
        ],
    }


@router.get("/meat-types")
def meat_types(session: SessionDep) -> list[dict[str, Any]]:
    rows = session.execute(
        select(Meat.type, func.count(Cook.id))
        .join(Cook, Cook.meat_id == Meat.id)
        .where(Cook.ended_at.is_not(None), Cook.status != "planned")
        .group_by(Meat.type)
        .order_by(Meat.type)
    )
    return [{"meat_type": meat_type, "count": count} for meat_type, count in rows]
