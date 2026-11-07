from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator
from datetime import UTC, date, datetime
from io import StringIO
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.channel_samples import compatibility_values
from app.deps import get_session
from app.models import (
    Channel,
    ChannelReading,
    Cook,
    Event,
    Fuel,
    Meat,
    Note,
    Photo,
    Profile,
    ProfileStep,
    Sample,
)
from app.routes.cooks import _cook_json, _iso
from app.routes.events import event_json
from app.service import as_utc

router = APIRouter(prefix="/api/export", tags=["export"])
SessionDep = Annotated[Session, Depends(get_session)]

COOK_HEADERS = [
    "id",
    "started_at",
    "startup_ended_at",
    "cook_ended_at",
    "cooldown_ended_at",
    "ended_at",
    "status",
    "startup_duration_seconds",
    "cook_duration_seconds",
    "cooldown_duration_seconds",
    "grill_duration_seconds",
    "time_to_done_seconds",
    "effective_setpoint",
    "rotisserie",
    "spices",
    "seasonings",
    "sauces",
    "prep_time_minutes",
    "results_text",
    "pellets_used_lb",
    "has_gap",
    "incomplete",
    "exclude_from_stats",
    "meat_type",
    "meat_pounds",
    "meat_price_per_pound",
    "meat_store",
    "meat_purchased_on",
    "pellet_vendor",
    "pellet_product_name",
    "pellet_price_per_pound",
    "profile_name",
]
SAMPLE_HEADERS = [
    "ts",
    "elapsed_seconds",
    "pit_temp",
    "setpoint",
    "probe1",
    "probe2",
    "probe1_target",
    "probe2_target",
    "fire_state",
    "power_state",
    "hvac_mode",
]


def _safe_cell(value: object) -> object:
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def _csv_lines(headers: list[str], rows: Iterable[Iterable[object]]) -> Iterator[str]:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([_safe_cell(header) for header in headers])
    yield output.getvalue()
    for row in rows:
        output.seek(0)
        output.truncate(0)
        writer.writerow([_safe_cell(value) for value in row])
        yield output.getvalue()


def _attachment(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


def _today() -> date:
    return datetime.now(UTC).date()


@router.get("/cooks.csv")
def cooks_csv(
    request: Request,
    session: SessionDep,
    meat_id: int | None = None,
    pellet_id: int | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
) -> StreamingResponse:
    query = (
        select(Cook, Meat, Fuel, Profile)
        .outerjoin(Meat, Cook.meat_id == Meat.id)
        .outerjoin(Fuel, Cook.fuel_id == Fuel.id)
        .outerjoin(Profile, Cook.profile_id == Profile.id)
    )
    if meat_id is not None:
        query = query.where(Cook.meat_id == meat_id)
    if pellet_id is not None:
        query = query.where(Cook.fuel_id == pellet_id)
    if status_filter is not None:
        query = query.where(Cook.status == status_filter)
    else:
        query = query.where(Cook.status != "planned")
    factory: sessionmaker[Session] = request.app.state.sessions
    query = query.order_by(Cook.started_at.desc()).execution_options(yield_per=100)

    def values() -> Iterator[list[object]]:
        with factory() as stream_session:
            rows = stream_session.execute(query)
            for cook, meat, pellet, profile in rows:
                yield [
                    cook.id,
                    _iso(cook.started_at),
                    _iso(cook.startup_ended_at),
                    _iso(cook.cook_ended_at),
                    _iso(cook.cooldown_ended_at),
                    _iso(cook.ended_at),
                    cook.status,
                    cook.startup_duration_seconds,
                    cook.cook_duration_seconds,
                    cook.cooldown_duration_seconds,
                    cook.grill_duration_seconds,
                    cook.time_to_done_seconds,
                    cook.effective_setpoint,
                    cook.rotisserie,
                    ", ".join(f"{spice.brand} {spice.name}" for spice in cook.spices),
                    cook.seasonings,
                    cook.sauces,
                    cook.prep_time_minutes,
                    cook.results_text,
                    cook.pellets_used_lb,
                    cook.has_gap,
                    cook.incomplete,
                    cook.exclude_from_stats,
                    meat.type if meat else None,
                    meat.pounds if meat else None,
                    meat.price_per_pound if meat else None,
                    meat.store if meat else None,
                    meat.purchased_on if meat else None,
                    pellet.vendor if pellet else None,
                    pellet.product_name if pellet else None,
                    pellet.price_per_pound if pellet else None,
                    profile.name if profile else None,
                ]

    return StreamingResponse(
        _csv_lines(COOK_HEADERS, values()),
        media_type="text/csv; charset=utf-8",
        headers=_attachment(f"smoke-stack-cooks-{_today().isoformat()}.csv"),
    )


@router.get("/cooks/{cook_id}/samples.csv")
def samples_csv(cook_id: int, request: Request, session: SessionDep) -> StreamingResponse:
    cook = session.get(Cook, cook_id)
    if cook is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cook not found")
    extras = sorted(
        session.scalars(
            select(Channel.key)
            .join(ChannelReading, ChannelReading.channel_id == Channel.id)
            .join(Sample, Sample.id == ChannelReading.sample_id)
            .where(
                Sample.cook_id == cook_id,
                Channel.key.not_in(("pit", "probe1", "probe2")),
            )
            .distinct()
        )
    )
    if not extras:
        legacy_names: set[str] = set()
        for probes in session.scalars(select(Sample.extra_probes).where(Sample.cook_id == cook_id)):
            legacy_names.update(probes or {})
        extras = sorted(legacy_names)
    sample_query = (
        select(Sample)
        .where(Sample.cook_id == cook_id)
        .order_by(Sample.ts)
        .execution_options(yield_per=500)
    )
    factory: sessionmaker[Session] = request.app.state.sessions
    started_at = cook.started_at
    if started_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Planned cooks cannot have samples")

    def values() -> Iterator[list[object]]:
        with factory() as stream_session:
            for sample in stream_session.scalars(sample_query):
                sample_values = compatibility_values(sample)
                yield [
                    _iso(sample.ts),
                    int((as_utc(sample.ts) - as_utc(started_at)).total_seconds()),
                    sample_values["pit_temp"],
                    sample_values["setpoint"],
                    sample_values["probe1"],
                    sample_values["probe2"],
                    sample_values["probe1_target"],
                    sample_values["probe2_target"],
                    sample.fire_state,
                    sample.power_state,
                    sample.hvac_mode,
                    *(sample_values["extra_probes"].get(name) for name in extras),
                ]

    return StreamingResponse(
        _csv_lines(SAMPLE_HEADERS + extras, values()),
        media_type="text/csv; charset=utf-8",
        headers=_attachment(f"smoke-stack-cook-{cook_id}-samples-{_today().isoformat()}.csv"),
    )


def _all_json(session: Session) -> dict[str, Any]:
    cooks: list[dict[str, Any]] = []
    for cook in session.scalars(select(Cook).order_by(Cook.id)):
        item = _cook_json(cook, session)
        item.update(created_at=_iso(cook.created_at), updated_at=_iso(cook.updated_at))
        item["events"] = (
            [
                {"cook_id": event.cook_id, **event_json(event, cook.started_at)}
                for event in session.scalars(
                    select(Event).where(Event.cook_id == cook.id).order_by(Event.ts, Event.id)
                )
            ]
            if cook.started_at is not None
            else []
        )
        item["photos"] = [
            {
                "id": photo.id,
                "cook_id": photo.cook_id,
                "event_id": photo.event_id,
                "caption": photo.caption,
                "url": f"/api/photos/{photo.id}/file",
            }
            for photo in session.scalars(
                select(Photo).where(Photo.cook_id == cook.id).order_by(Photo.id)
            )
        ]
        cooks.append(item)

    profiles = []
    for profile in session.scalars(select(Profile).order_by(Profile.id)):
        profiles.append(
            {
                "id": profile.id,
                "name": profile.name,
                "keep_warm": profile.keep_warm,
                "keep_warm_temp": profile.keep_warm_temp,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
                "steps": [
                    {
                        "id": step.id,
                        "position": step.position,
                        "grill_temp": step.grill_temp,
                        "stop_mode": step.stop_mode,
                        "duration_minutes": step.duration_minutes,
                        "probe": step.probe,
                        "target_temp": step.target_temp,
                        "instructions": step.instructions,
                    }
                    for step in session.scalars(
                        select(ProfileStep)
                        .where(ProfileStep.profile_id == profile.id)
                        .order_by(ProfileStep.position, ProfileStep.id)
                    )
                ],
            }
        )

    return {
        "cooks": cooks,
        "meat": list(session.scalars(select(Meat).order_by(Meat.id))),
        "fuel": list(session.scalars(select(Fuel).order_by(Fuel.id))),
        "profiles": profiles,
        "notes": list(session.scalars(select(Note).order_by(Note.id))),
    }


@router.get("/all.json")
def all_json(session: SessionDep) -> JSONResponse:
    return JSONResponse(
        jsonable_encoder(_all_json(session)),
        headers=_attachment(f"smoke-stack-{_today().isoformat()}.json"),
    )
