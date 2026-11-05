from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from email.utils import formatdate
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from starlette.background import BackgroundTask
from starlette.types import ASGIApp, Receive, Scope, Send

from app.backup import build_backup
from app.config import Settings
from app.database import make_engine, make_session_factory
from app.deps import get_session
from app.grill_profiles import load_grill_profiles
from app.ha import HAClient, HAStatus, HomeAssistantClient, ingest
from app.models import Cook, Sample
from app.restore import restore_backup
from app.routes.cooks import router as cooks_router
from app.routes.events import router as events_router
from app.routes.export import router as export_router
from app.routes.grills import router as grills_router
from app.routes.meat import router as meat_router
from app.routes.meat_groups import router as meat_groups_router
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
BUILD_INFO_PATH = Path(__file__).with_name("build_info.txt")
STATIC_INDEX_PATH = Path(__file__).parent / "static" / "index.html"
INGRESS_PATH_PATTERN = re.compile(r"^/api/hassio_ingress/[A-Za-z0-9_-]+$")


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


class CollapseLeadingSlashesMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith("//"):
            scope = dict(scope)
            scope["path"] = "/" + scope["path"].lstrip("/")
            raw_path = scope.get("raw_path")
            if raw_path is not None:
                scope["raw_path"] = b"/" + raw_path.lstrip(b"/")
        await self.app(scope, receive, send)


def create_app(
    settings: Settings | None = None,
    sessions: sessionmaker[Session] | None = None,
    ha_client: HAClient | None = None,
) -> FastAPI:
    config = settings or Settings.from_env()
    grill_profiles = load_grill_profiles(config.grill_profiles_path)
    factory = sessions or make_session_factory(make_engine(config.database_path))
    service = CookService(
        factory,
        sample_interval_seconds=config.sample_interval_seconds,
        incomplete_timeout_minutes=config.incomplete_timeout_minutes,
        data_gap_event_min_seconds=config.data_gap_event_min_seconds,
    )
    client = ha_client
    connection = config.ha_connection
    ha_status = HAStatus(configured=connection is not None)
    if client is None and connection is not None:
        client = HomeAssistantClient(
            connection.websocket_url,
            connection.token,
            config.load_entities(),
            config.sample_interval_seconds,
            config.ha_ws_max_size_bytes,
            template_url=connection.template_url,
            host=connection.host,
        )
    if client is not None:
        ha_status = client.status

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        Path(config.photo_dir).mkdir(parents=True, exist_ok=True)
        seed_spices(factory)
        if connection is None:
            logger.warning(
                "HA_URL/HA_TOKEN or SUPERVISOR_TOKEN not set; Home Assistant ingest disabled"
            )
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
    app.add_middleware(CollapseLeadingSlashesMiddleware)

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

    @app.get("/api/backup", response_class=FileResponse)
    def backup() -> FileResponse:
        created_at = datetime.now(UTC)
        archive_path = build_backup(
            config.database_path,
            config.photo_dir,
            Path(config.photo_dir).parent / "showcase",
            _version(),
            created_at=created_at,
        )
        filename = f"smoke-shack-backup-{created_at.strftime('%Y%m%d-%H%M%S')}.zip"
        return FileResponse(
            archive_path,
            media_type="application/zip",
            filename=filename,
            background=BackgroundTask(archive_path.unlink, missing_ok=True),
        )

    @app.post("/api/restore")
    async def restore(file: UploadFile = File(...)) -> dict[str, Any]:
        return await restore_backup(
            file,
            Path(config.database_path),
            Path(config.photo_dir),
            Path(config.photo_dir).parent / "showcase",
            factory,
            _version(),
            config.restore_max_bytes,
        )

    app.state.sessions = factory
    app.state.photo_dir = Path(config.photo_dir)
    app.state.showcase_dir = Path(config.photo_dir).parent / "showcase"
    app.state.cook_service = service
    app.state.grill_profiles = grill_profiles
    app.state.ha_client = client
    app.include_router(meat_router)
    app.include_router(meat_groups_router)
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
    app.include_router(grills_router)

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> Response:
        ingress_path = request.headers.get("X-Ingress-Path", "")
        base_path = ingress_path if INGRESS_PATH_PATTERN.fullmatch(ingress_path) else ""
        content = STATIC_INDEX_PATH.read_text(encoding="utf-8").replace(
            "<head>", f'<head>\n    <base href="{base_path}/">', 1
        )
        stat = STATIC_INDEX_PATH.stat()
        etag = f'"{hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()}"'
        headers = {
            "Cache-Control": "no-cache",
            "ETag": etag,
            "Last-Modified": formatdate(stat.st_mtime, usegmt=True),
        }
        if request.headers.get("If-None-Match") == etag:
            return Response(status_code=304, headers=headers)
        return HTMLResponse(content, headers=headers)

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
        build_version = BUILD_INFO_PATH.read_text(encoding="utf-8").splitlines()[0].strip()
    except (OSError, IndexError):
        return "dev"
    return build_version or "dev"
