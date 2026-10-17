from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.database import make_engine, make_session_factory
from app.deps import get_session
from app.ha import HAClient, HAStatus, HomeAssistantClient
from app.models import Cook, Sample
from app.routes.cooks import router as cooks_router
from app.routes.events import router as events_router
from app.routes.meat import router as meat_router
from app.routes.notes import router as notes_router
from app.routes.pellets import router as pellets_router
from app.routes.profiles import router as profiles_router
from app.service import CookService, as_utc

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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
    ha_status = HAStatus(configured=bool(config.ha_url and config.ha_token))
    if client is None and config.ha_url and config.ha_token:
        client = HomeAssistantClient(
            config.ha_url,
            config.ha_token,
            config.load_entities(),
            config.sample_interval_seconds,
            config.ha_ws_max_size_bytes,
        )
    if client is not None:
        ha_status = client.status

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        Path(config.photo_dir).mkdir(parents=True, exist_ok=True)
        if not config.ha_url or not config.ha_token:
            logger.warning("HA_URL/HA_TOKEN not set; Home Assistant ingest disabled")
        task = asyncio.create_task(consume(client, service)) if client else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    app = FastAPI(title="Smoke Stack", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/status")
    def status(session: Session = Depends(get_session)) -> dict[str, Any]:
        active = session.scalar(
            select(Cook).where(Cook.ended_at.is_(None)).order_by(Cook.started_at.desc())
        )
        last_sample = session.scalar(select(Sample.ts).order_by(Sample.ts.desc()).limit(1))
        return {
            "ha": {
                "configured": ha_status.configured,
                "connected": ha_status.connected,
                "last_error": ha_status.last_error,
                "last_event_at": _iso(ha_status.last_event_at),
            },
            "ingest": {
                "last_sample_at": _iso(last_sample),
                "sample_interval_seconds": config.sample_interval_seconds,
            },
            "active_cook": (
                {
                    "id": active.id,
                    "phase": active.status,
                    "started_at": _iso(active.started_at),
                }
                if active is not None
                else None
            ),
            "version": _version(),
        }

    app.state.sessions = factory
    app.state.cook_service = service
    app.include_router(meat_router)
    app.include_router(pellets_router)
    app.include_router(notes_router)
    app.include_router(events_router)
    app.include_router(profiles_router)
    app.include_router(cooks_router)
    return app


def _iso(value: datetime | None) -> str | None:
    return as_utc(value).isoformat().replace("+00:00", "Z") if value else None


def _version() -> str:
    try:
        return version("smoke-stack")
    except PackageNotFoundError:
        return "0.1.0"
