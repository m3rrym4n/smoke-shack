from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.database import make_engine, make_session_factory
from app.ha import HAClient, HomeAssistantClient
from app.models import Cook, Event, Sample
from app.service import CookService, as_utc


async def consume(client: HAClient, service: CookService) -> None:
    async for snapshot in client.snapshots():
        service.process(snapshot)


def create_app(
    settings: Settings | None = None,
    sessions: sessionmaker[Session] | None = None,
    ha_client: HAClient | None = None,
) -> FastAPI:
    config = settings or Settings.from_env()
    factory = sessions or make_session_factory(make_engine(config.database_path))
    service = CookService(
        factory,
        sample_interval_seconds=config.sample_interval_seconds,
        incomplete_timeout_minutes=config.incomplete_timeout_minutes,
    )
    client = ha_client
    if client is None and config.ha_url and config.ha_token:
        client = HomeAssistantClient(
            config.ha_url,
            config.ha_token,
            config.load_entities(),
            config.sample_interval_seconds,
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        Path(config.photo_dir).mkdir(parents=True, exist_ok=True)
        task = asyncio.create_task(consume(client, service)) if client else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    app = FastAPI(title="Smoke Stack", lifespan=lifespan)

    def get_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/cooks")
    def cooks(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
        query = select(Cook).order_by(Cook.started_at.desc())
        return [_cook(item) for item in session.scalars(query)]

    @app.get("/api/cooks/{cook_id}")
    def cook(cook_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
        item = session.get(Cook, cook_id)
        if item is None:
            raise HTTPException(404, "Cook not found")
        return _cook(item)

    @app.get("/api/cooks/{cook_id}/samples")
    def samples(cook_id: int, session: Session = Depends(get_session)) -> list[dict[str, Any]]:
        item = session.get(Cook, cook_id)
        if item is None:
            raise HTTPException(404, "Cook not found")
        rows = session.scalars(select(Sample).where(Sample.cook_id == cook_id).order_by(Sample.ts))
        return [_sample(row, item.started_at) for row in rows]

    @app.get("/api/cooks/{cook_id}/events")
    def events(cook_id: int, session: Session = Depends(get_session)) -> list[dict[str, Any]]:
        item = session.get(Cook, cook_id)
        if item is None:
            raise HTTPException(404, "Cook not found")
        rows = session.scalars(select(Event).where(Event.cook_id == cook_id).order_by(Event.ts))
        return [_event(row, item.started_at) for row in rows]

    app.state.sessions = factory
    app.state.cook_service = service
    return app


def _iso(value: datetime | None) -> str | None:
    return as_utc(value).isoformat().replace("+00:00", "Z") if value else None


def _cook(cook: Cook) -> dict[str, Any]:
    return {
        "id": cook.id,
        "started_at": _iso(cook.started_at),
        "startup_ended_at": _iso(cook.startup_ended_at),
        "cook_ended_at": _iso(cook.cook_ended_at),
        "cooldown_ended_at": _iso(cook.cooldown_ended_at),
        "ended_at": _iso(cook.ended_at),
        "status": cook.status,
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


def _sample(sample: Sample, started: datetime) -> dict[str, Any]:
    return {
        "id": sample.id,
        "ts": _iso(sample.ts),
        "elapsed_seconds": int((as_utc(sample.ts) - as_utc(started)).total_seconds()),
        "pit_temp": sample.pit_temp,
        "setpoint": sample.setpoint,
        "probe1": sample.probe1,
        "probe2": sample.probe2,
        "extra_probes": sample.extra_probes,
        "fire_state": sample.fire_state,
        "power_state": sample.power_state,
        "hvac_mode": sample.hvac_mode,
    }


def _event(event: Event, started: datetime) -> dict[str, Any]:
    return {
        "id": event.id,
        "ts": _iso(event.ts),
        "elapsed_seconds": int((as_utc(event.ts) - as_utc(started)).total_seconds()),
        "kind": event.kind,
        "source": event.source,
        "title": event.title,
        "description": event.description,
        "data": event.data,
        "photo_path": event.photo_path,
    }
