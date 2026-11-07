from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, selectinload

from app.channel_samples import channel_payload, compatibility_values
from app.deps import get_session
from app.equipment import first_equipment_id
from app.models import (
    ChannelReading,
    Cook,
    Equipment,
    Event,
    Fuel,
    Meat,
    Note,
    Photo,
    Profile,
    Sample,
    Spice,
)
from app.routes.events import event_json
from app.schemas import CookUpdate, PlannedCookCreate
from app.service import as_utc

router = APIRouter(prefix="/api/cooks", tags=["cooks"])
SessionDep = Annotated[Session, Depends(get_session)]


def _iso(value: datetime | None) -> str | None:
    return as_utc(value).isoformat().replace("+00:00", "Z") if value else None


def _get_cook(cook_id: int, session: Session) -> Cook:
    cook = session.get(Cook, cook_id)
    if cook is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cook not found")
    return cook


def _cook_json(cook: Cook, session: Session, *, include_cost: bool = False) -> dict[str, Any]:
    equipment = (
        session.get(Equipment, cook.equipment_id) if cook.equipment_id is not None else None
    )
    meat = session.get(Meat, cook.meat_id) if cook.meat_id is not None else None
    fuel = session.get(Fuel, cook.fuel_id) if cook.fuel_id is not None else None
    profile = session.get(Profile, cook.profile_id) if cook.profile_id is not None else None
    latest_sample = session.scalar(
        select(Sample)
        .options(selectinload(Sample.channel_readings).selectinload(ChannelReading.channel))
        .where(Sample.cook_id == cook.id)
        .order_by(Sample.ts.desc(), Sample.id.desc())
        .limit(1)
    )
    latest_values = compatibility_values(latest_sample) if latest_sample is not None else None
    current_setpoint = (
        latest_values["setpoint"]
        if latest_values is not None and cook.ended_at is None and cook.status != "planned"
        else None
    )
    result: dict[str, Any] = {
        "id": cook.id,
        "created_at": _iso(cook.created_at),
        "started_at": _iso(cook.started_at),
        "startup_ended_at": _iso(cook.startup_ended_at),
        "cook_ended_at": _iso(cook.cook_ended_at),
        "cooldown_ended_at": _iso(cook.cooldown_ended_at),
        "ended_at": _iso(cook.ended_at),
        "status": cook.status,
        "state": cook.status,
        "meat_id": cook.meat_id,
        "fuel_id": cook.fuel_id,
        "pellet_id": cook.fuel_id,
        "profile_id": cook.profile_id,
        "equipment_id": cook.equipment_id,
        "grill_manufacturer": equipment.maker if equipment is not None else None,
        "grill_model": equipment.model if equipment is not None else None,
        "grill_photo_url": (
            f"/api/equipment/{equipment.id}/photo"
            if equipment is not None and equipment.photo_path is not None
            else None
        ),
        "grill_logo_url": (
            f"/api/equipment/{equipment.id}/logo"
            if equipment is not None and equipment.logo_path is not None
            else None
        ),
        "rotisserie": cook.rotisserie,
        "seasonings": cook.seasonings,
        "spices": [
            {
                "id": spice.id,
                "name": spice.name,
                "brand": spice.brand,
                "category": spice.brand,
                "is_custom": spice.is_custom,
                "photo_url": spice.photo_url,
            }
            for spice in cook.spices
        ],
        "sauces": cook.sauces,
        "prep_time_minutes": cook.prep_time_minutes,
        "results_text": cook.results_text,
        "pellets_used_lb": cook.pellets_used_lb,
        "meat": (
            {
                "id": meat.id,
                "type": meat.type,
                "pounds": float(meat.pounds),
                "price_per_pound": float(meat.price_per_pound),
                "store": meat.store,
                "purchased_on": meat.purchased_on.isoformat(),
            }
            if meat is not None
            else None
        ),
        "fuel": (
            {
                "id": fuel.id,
                "type": fuel.type,
                "vendor": fuel.vendor,
                "product_name": fuel.product_name,
                "price_per_pound": (
                    float(fuel.price_per_pound) if fuel.price_per_pound is not None else None
                ),
            }
            if fuel is not None
            else None
        ),
        "profile_name": profile.name if profile is not None else None,
        "startup_duration_seconds": cook.startup_duration_seconds,
        "cook_duration_seconds": cook.cook_duration_seconds,
        "cooldown_duration_seconds": cook.cooldown_duration_seconds,
        "grill_duration_seconds": cook.grill_duration_seconds,
        "aggregate_setpoint": cook.aggregate_setpoint,
        "setpoint_override": cook.setpoint_override,
        "effective_setpoint": cook.effective_setpoint,
        "current_setpoint": current_setpoint,
        "channels": channel_payload(latest_sample) if latest_sample is not None else [],
        "time_to_done_seconds": cook.time_to_done_seconds,
        "has_gap": cook.has_gap,
        "incomplete": cook.incomplete,
        "exclude_from_stats": cook.exclude_from_stats,
    }
    if include_cost:
        meat_cost = meat.pounds * meat.price_per_pound if meat is not None else None
        fuel_cost = (
            Decimal(str(cook.pellets_used_lb)) * fuel.price_per_pound
            if (
                fuel is not None
                and fuel.price_per_pound is not None
                and cook.pellets_used_lb is not None
            )
            else None
        )
        result["cost"] = {
            "meat_cost": float(round(meat_cost, 2)) if meat_cost is not None else None,
            "pellet_cost": float(round(fuel_cost, 2)) if fuel_cost is not None else None,
        }
    # Pellet fields remain until the pantry UI moves to the fuel API.
    result["pellet"] = result["fuel"] if fuel is not None and fuel.type == "pellets" else None
    return result


@router.get("")
def list_cooks(
    session: SessionDep,
    meat_id: int | None = None,
    fuel_id: int | None = None,
    pellet_id: int | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    state: str | None = None,
    limit: int = Query(default=50, ge=1),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    query = select(Cook)
    if meat_id is not None:
        query = query.where(Cook.meat_id == meat_id)
    requested_fuel_id = fuel_id if fuel_id is not None else pellet_id
    if requested_fuel_id is not None:
        query = query.where(Cook.fuel_id == requested_fuel_id)
    requested_state = state if state is not None else status_filter
    if requested_state is not None:
        query = query.where(Cook.status == requested_state)
    query = (
        query.order_by(Cook.started_at.desc(), Cook.created_at.desc(), Cook.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [_cook_json(cook, session) for cook in session.scalars(query)]


def _validate_references(changes: dict[str, Any], session: Session) -> None:
    references = (
        ("equipment_id", Equipment, "Equipment"),
        ("meat_id", Meat, "Meat"),
        ("fuel_id", Fuel, "Fuel"),
        ("profile_id", Profile, "Profile"),
    )
    for field, model, label in references:
        value = changes.get(field)
        if value is not None and session.get(model, value) is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{label} not found")


def _get_spices(spice_ids: list[int], session: Session) -> list[Spice]:
    unique_ids = set(spice_ids)
    spices = list(session.scalars(select(Spice).where(Spice.id.in_(unique_ids))))
    if len(spices) != len(unique_ids):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Spice not found")
    return spices


@router.post("", status_code=status.HTTP_201_CREATED)
def create_planned_cook(payload: PlannedCookCreate, session: SessionDep) -> dict[str, Any]:
    values = payload.model_dump(exclude={"state", "spice_ids"})
    legacy_fuel_id = values.pop("pellet_id", None)
    if values.get("fuel_id") is None:
        values["fuel_id"] = legacy_fuel_id
    _validate_references(values, session)
    cook = Cook(
        started_at=None,
        status="planned",
        equipment_id=first_equipment_id(session),
        **values,
    )
    cook.spices = _get_spices(payload.spice_ids, session)
    session.add(cook)
    session.commit()
    session.refresh(cook)
    return _cook_json(cook, session, include_cost=True)


@router.get("/next")
def next_planned_cook(session: SessionDep) -> dict[str, Any]:
    cook = session.scalar(
        select(Cook).where(Cook.status == "planned").order_by(Cook.created_at, Cook.id).limit(1)
    )
    if cook is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No planned cook")
    return _cook_json(cook, session, include_cost=True)


@router.get("/{cook_id}")
def get_cook(cook_id: int, session: SessionDep) -> dict[str, Any]:
    return _cook_json(_get_cook(cook_id, session), session, include_cost=True)


@router.patch("/{cook_id}")
def update_cook(cook_id: int, payload: CookUpdate, session: SessionDep) -> dict[str, Any]:
    cook = _get_cook(cook_id, session)
    changes = payload.model_dump(exclude_unset=True)
    legacy_fuel_id = changes.pop("pellet_id", None)
    if "fuel_id" not in changes and legacy_fuel_id is not None:
        changes["fuel_id"] = legacy_fuel_id
    spice_ids = changes.pop("spice_ids", None)
    _validate_references(changes, session)
    for field, value in changes.items():
        setattr(cook, field, value)
    if spice_ids is not None:
        cook.spices = _get_spices(spice_ids, session)
    session.commit()
    session.refresh(cook)
    return _cook_json(cook, session, include_cost=True)


@router.delete("/{cook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cook(cook_id: int, session: SessionDep, request: Request) -> Response:
    cook = _get_cook(cook_id, session)
    if cook.ended_at is None and cook.status != "planned":
        raise HTTPException(status.HTTP_409_CONFLICT, "Active cook cannot be deleted")
    photo_paths = list(session.scalars(select(Photo.path).where(Photo.cook_id == cook_id)))
    session.execute(delete(Photo).where(Photo.cook_id == cook_id))
    session.execute(delete(Event).where(Event.cook_id == cook_id))
    session.execute(delete(Sample).where(Sample.cook_id == cook_id))
    session.execute(update(Note).where(Note.cook_id == cook_id).values(cook_id=None))
    session.delete(cook)
    session.commit()
    for photo_path in photo_paths:
        Path(photo_path).unlink(missing_ok=True)
    cook_photo_dir = request.app.state.photo_dir / str(cook_id)
    try:
        cook_photo_dir.rmdir()
    except OSError:
        pass
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{cook_id}/samples")
def samples(cook_id: int, session: SessionDep) -> list[dict[str, Any]]:
    cook = _get_cook(cook_id, session)
    rows = session.scalars(
        select(Sample)
        .options(selectinload(Sample.channel_readings).selectinload(ChannelReading.channel))
        .where(Sample.cook_id == cook_id)
        .order_by(Sample.ts)
    )
    return [_sample_json(row, cook.started_at) for row in rows]


def _sample_json(sample: Sample, started: datetime | None) -> dict[str, Any]:
    if started is None:
        raise ValueError("planned cooks cannot have samples")
    values = compatibility_values(sample)
    return {
        "id": sample.id,
        "ts": _iso(sample.ts),
        "elapsed_seconds": int((as_utc(sample.ts) - as_utc(started)).total_seconds()),
        **values,
        "channels": channel_payload(sample),
        "fire_state": sample.fire_state,
        "power_state": sample.power_state,
        "hvac_mode": sample.hvac_mode,
    }


@router.get("/{cook_id}/events")
def events(cook_id: int, session: SessionDep) -> list[dict[str, Any]]:
    cook = _get_cook(cook_id, session)
    if cook.started_at is None:
        return []
    rows = session.scalars(select(Event).where(Event.cook_id == cook_id).order_by(Event.ts))
    return [event_json(row, cook.started_at) for row in rows]
