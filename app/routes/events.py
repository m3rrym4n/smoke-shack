from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.deps import get_session
from app.models import Cook, Event, utc_now
from app.schemas import EventResponse, UserEventCreate, UserEventUpdate
from app.service import as_utc

router = APIRouter(tags=["events"])
SessionDep = Annotated[Session, Depends(get_session)]


def _get_cook(cook_id: int, session: Session) -> Cook:
    cook = session.get(Cook, cook_id)
    if cook is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cook not found")
    return cook


def _get_event(event_id: int, session: Session) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    if event.source != "user":
        raise HTTPException(status.HTTP_409_CONFLICT, "Automatic events are read-only")
    return event


def event_json(event: Event, started_at: datetime) -> dict[str, Any]:
    return {
        "id": event.id,
        "ts": as_utc(event.ts),
        "elapsed_seconds": int((as_utc(event.ts) - as_utc(started_at)).total_seconds()),
        "kind": event.kind,
        "source": event.source,
        "title": event.title,
        "description": event.description,
        "data": event.data,
        "photo_path": event.photo_path,
    }


def _validate_ts(ts: datetime, cook: Cook) -> None:
    if as_utc(ts) < as_utc(cook.started_at):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Event timestamp cannot be before cook start",
        )


@router.post(
    "/api/cooks/{cook_id}/events",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_event(cook_id: int, payload: UserEventCreate, session: SessionDep) -> dict[str, Any]:
    cook = _get_cook(cook_id, session)
    event_ts = payload.ts or utc_now()
    _validate_ts(event_ts, cook)
    event = Event(
        cook_id=cook.id,
        ts=event_ts,
        kind="user",
        source="user",
        title=payload.title,
        description=payload.description,
        data={},
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event_json(event, cook.started_at)


@router.patch("/api/events/{event_id}", response_model=EventResponse)
def update_event(event_id: int, payload: UserEventUpdate, session: SessionDep) -> dict[str, Any]:
    event = _get_event(event_id, session)
    cook = _get_cook(event.cook_id, session)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("ts") is not None:
        _validate_ts(changes["ts"], cook)
    for field, value in changes.items():
        setattr(event, field, value)
    session.commit()
    session.refresh(event)
    return event_json(event, cook.started_at)


@router.delete("/api/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: int, session: SessionDep) -> Response:
    session.delete(_get_event(event_id, session))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
