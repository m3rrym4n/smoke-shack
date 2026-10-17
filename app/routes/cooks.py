from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.deps import get_session
from app.models import Cook, Event, Meat, Note, Pellet, Photo, Profile, Sample
from app.routes.events import event_json
from app.schemas import CookUpdate
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
    meat = session.get(Meat, cook.meat_id) if cook.meat_id is not None else None
    pellet = session.get(Pellet, cook.pellet_id) if cook.pellet_id is not None else None
    profile = session.get(Profile, cook.profile_id) if cook.profile_id is not None else None
    result: dict[str, Any] = {
        "id": cook.id,
        "started_at": _iso(cook.started_at),
        "startup_ended_at": _iso(cook.startup_ended_at),
        "cook_ended_at": _iso(cook.cook_ended_at),
        "cooldown_ended_at": _iso(cook.cooldown_ended_at),
        "ended_at": _iso(cook.ended_at),
        "status": cook.status,
        "meat_id": cook.meat_id,
        "pellet_id": cook.pellet_id,
        "profile_id": cook.profile_id,
        "rotisserie": cook.rotisserie,
        "seasonings": cook.seasonings,
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
        "pellet": (
            {
                "id": pellet.id,
                "vendor": pellet.vendor,
                "product_name": pellet.product_name,
                "price_per_pound": float(pellet.price_per_pound),
            }
            if pellet is not None
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
        "time_to_done_seconds": cook.time_to_done_seconds,
        "has_gap": cook.has_gap,
        "incomplete": cook.incomplete,
    }
    if include_cost:
        meat_cost = meat.pounds * meat.price_per_pound if meat is not None else None
        pellet_cost = (
            Decimal(str(cook.pellets_used_lb)) * pellet.price_per_pound
            if pellet is not None and cook.pellets_used_lb is not None
            else None
        )
        result["cost"] = {
            "meat_cost": float(round(meat_cost, 2)) if meat_cost is not None else None,
            "pellet_cost": float(round(pellet_cost, 2)) if pellet_cost is not None else None,
        }
    return result


@router.get("")
def list_cooks(
    session: SessionDep,
    meat_id: int | None = None,
    pellet_id: int | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    query = select(Cook)
    if meat_id is not None:
        query = query.where(Cook.meat_id == meat_id)
    if pellet_id is not None:
        query = query.where(Cook.pellet_id == pellet_id)
    if status_filter is not None:
        query = query.where(Cook.status == status_filter)
    query = query.order_by(Cook.started_at.desc()).limit(limit).offset(offset)
    return [_cook_json(cook, session) for cook in session.scalars(query)]


@router.get("/{cook_id}")
def get_cook(cook_id: int, session: SessionDep) -> dict[str, Any]:
    return _cook_json(_get_cook(cook_id, session), session, include_cost=True)


@router.patch("/{cook_id}")
def update_cook(cook_id: int, payload: CookUpdate, session: SessionDep) -> dict[str, Any]:
    cook = _get_cook(cook_id, session)
    changes = payload.model_dump(exclude_unset=True)
    references = (
        ("meat_id", Meat, "Meat"),
        ("pellet_id", Pellet, "Pellet"),
        ("profile_id", Profile, "Profile"),
    )
    for field, model, label in references:
        value = changes.get(field)
        if value is not None and session.get(model, value) is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{label} not found")
    for field, value in changes.items():
        setattr(cook, field, value)
    session.commit()
    session.refresh(cook)
    return _cook_json(cook, session, include_cost=True)


@router.delete("/{cook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cook(cook_id: int, session: SessionDep, request: Request) -> Response:
    cook = _get_cook(cook_id, session)
    if cook.ended_at is None:
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
    rows = session.scalars(select(Sample).where(Sample.cook_id == cook_id).order_by(Sample.ts))
    return [_sample_json(row, cook.started_at) for row in rows]


def _sample_json(sample: Sample, started: datetime) -> dict[str, Any]:
    return {
        "id": sample.id,
        "ts": _iso(sample.ts),
        "elapsed_seconds": int((as_utc(sample.ts) - as_utc(started)).total_seconds()),
        "pit_temp": sample.pit_temp,
        "setpoint": sample.setpoint,
        "probe1": sample.probe1,
        "probe2": sample.probe2,
        "probe1_target": sample.probe1_target,
        "probe2_target": sample.probe2_target,
        "extra_probes": sample.extra_probes,
        "fire_state": sample.fire_state,
        "power_state": sample.power_state,
        "hvac_mode": sample.hvac_mode,
    }


@router.get("/{cook_id}/events")
def events(cook_id: int, session: SessionDep) -> list[dict[str, Any]]:
    cook = _get_cook(cook_id, session)
    rows = session.scalars(select(Event).where(Event.cook_id == cook_id).order_by(Event.ts))
    return [event_json(row, cook.started_at) for row in rows]
