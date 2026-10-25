from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from starlette.types import Scope

from app.config import Settings
from app.database import make_engine, make_session_factory
from app.deps import get_session
from app.ha import HAClient, HAStatus, HomeAssistantClient, ingest
from app.models import Cook, Sample
from app.routes.cooks import router as cooks_router
from app.routes.events import router as events_router
from app.routes.export import router as export_router
from app.routes.meat import router as meat_router
from app.routes.notes import router as notes_router
from app.routes.pellets import router as pellets_router
from app.routes.photos import router as photos_router
from app.routes.profiles import router as profiles_router
from app.routes.showcase import router as showcase_router
from app.routes.spices import router as spices_router
from app.routes.stats import router as stats_router
from app.seed import seed_spices
from app.service import CookService, as_utc

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class RevalidatingStaticFiles(StaticFiles):
    def file_response(
        self,
        full_path: str | os.PathLike[str],
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        response.headers["Cache-Control"] = "no-cache"
        return response


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
        data_gap_event_min_seconds=config.data_gap_event_min_seconds,
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
        seed_spices(factory)
        if not config.ha_url or not config.ha_token:
            logger.warning("HA_URL/HA_TOKEN not set; Home Assistant ingest disabled")
        task = (
            asyncio.create_task(ingest(client, service, config.sample_interval_seconds))
            if client
            else None
        )
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
            select(Cook)
            .where(Cook.ended_at.is_(None), Cook.status != "planned")
            .order_by(Cook.started_at.desc())
        )
        last_sample = session.scalar(select(Sample.ts).order_by(Sample.ts.desc()).limit(1))
        fallback_name = ha_status.grill_name or config.grill_name.strip() or "My grill"
        return {
            "grill_name": fallback_name,
            "grill_title": ha_status.grill_title or fallback_name,
            "grill_maker": ha_status.grill_maker,
            "ha": {
                "configured": ha_status.configured,
                "connected": ha_status.connected,
                "last_error": ha_status.last_error,
                "last_event_at": _iso(ha_status.last_event_at),
            },
            "ingest": {
                "last_sample_at": _iso(last_sample),
                "sample_interval_seconds": config.sample_interval_seconds,
                "data_gap_event_min_seconds": config.data_gap_event_min_seconds,
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
    app.state.photo_dir = Path(config.photo_dir)
    app.state.showcase_dir = Path(config.photo_dir).parent / "showcase"
    app.state.cook_service = service
    app.include_router(meat_router)
    app.include_router(pellets_router)
    app.include_router(spices_router)
    app.include_router(notes_router)
    app.include_router(events_router)
    app.include_router(profiles_router)
    app.include_router(cooks_router)
    app.include_router(photos_router)
    app.include_router(showcase_router)
    app.include_router(stats_router)
    app.include_router(export_router)
    app.mount(
        "/",
        RevalidatingStaticFiles(directory=Path(__file__).parent / "static", html=True),
        name="static",
    )
    return app


def _iso(value: datetime | None) -> str | None:
    return as_utc(value).isoformat().replace("+00:00", "Z") if value else None


def _version() -> str:
    try:
        return version("smoke-stack")
    except PackageNotFoundError:
        return "0.1.0"
