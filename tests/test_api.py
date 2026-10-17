from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest
from conftest import FakeClock, FakeHAClient
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import create_app
from app.config import Settings
from app.ha import HAStatus
from app.service import CookService, GrillSnapshot


def test_health(sessions: sessionmaker[Session]) -> None:
    app = create_app(Settings(), sessions, FakeHAClient())
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_static_shell_and_existing_routes(sessions: sessionmaker[Session]) -> None:
    app = create_app(Settings(), sessions, FakeHAClient())
    with TestClient(app) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert "text/html" in home.headers["content-type"]
        assert "SMOKE-STACK" in home.text
        assert client.get("/health").status_code == 200
        assert client.get("/docs").status_code == 200


def test_live_view_static_assets_exist(sessions: sessionmaker[Session]) -> None:
    app = create_app(Settings(), sessions, FakeHAClient())
    with TestClient(app) as client:
        for path in (
            "/js/views/live.js",
            "/js/components/gauge.js",
            "/js/live-logic.js",
        ):
            response = client.get(path)
            assert response.status_code == 200
            assert "javascript" in response.headers["content-type"]


def test_status_with_ha_unconfigured(sessions: sessionmaker[Session]) -> None:
    app = create_app(Settings(), sessions)
    with TestClient(app) as client:
        status = client.get("/status").json()

    assert status["ha"]["configured"] is False
    assert status["ha"]["connected"] is False
    assert status["active_cook"] is None
    assert status["ingest"]["sample_interval_seconds"] == 10
    assert status["version"] == "0.1.0"


def test_status_after_simulated_connect(sessions: sessionmaker[Session]) -> None:
    fake = FakeHAClient()
    fake.status = HAStatus(
        configured=True,
        connected=True,
        last_event_at=datetime(2026, 10, 16, 16, 57, 3, tzinfo=UTC),
    )
    app = create_app(Settings(ha_url="http://ha", ha_token="secret"), sessions, fake)
    with TestClient(app) as client:
        status = client.get("/status").json()

    assert status["ha"]["connected"] is True
    assert status["ha"]["last_event_at"] == "2026-10-16T16:57:03Z"


def test_missing_token_startup_warns_and_serves_health(
    sessions: sessionmaker[Session], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    app = create_app(Settings(ha_url="http://ha", ha_token=""), sessions)
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}

    assert "HA_URL/HA_TOKEN not set; Home Assistant ingest disabled" in caplog.messages


def test_status_reports_active_cook(sessions: sessionmaker[Session], clock: FakeClock) -> None:
    service = CookService(sessions, clock)
    cook = service.process(
        GrillSnapshot(setpoint=150, fire_state="Startup", power_state="On", hvac_mode="heat")
    )
    assert cook is not None
    app = create_app(Settings(), sessions)
    with TestClient(app) as client:
        status = client.get("/status").json()
        assert status["active_cook"] == {
            "id": cook.id,
            "phase": "startup",
            "started_at": "2026-10-16T16:57:03Z",
        }

    clock.advance(minutes=1)
    service.process(
        GrillSnapshot(setpoint=150, fire_state="Cool Down", power_state="Fan", hvac_mode="off")
    )
    clock.advance(minutes=1)
    service.process(
        GrillSnapshot(setpoint=150, fire_state="Off", power_state="Off", hvac_mode="off")
    )
    with TestClient(app) as client:
        assert client.get("/status").json()["active_cook"] is None


def test_exact_timestamp_and_elapsed_seconds(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    service = CookService(sessions, clock)
    cook = service.process(
        GrillSnapshot(setpoint=150, fire_state="Startup", power_state="On", hvac_mode="heat")
    )
    assert cook is not None
    clock.advance(seconds=75)
    event_time = datetime(2026, 10, 16, 16, 58, 18, tzinfo=UTC)
    service.process(
        GrillSnapshot(setpoint=275, fire_state="Running", power_state="On", hvac_mode="heat"),
        event_time,
    )
    app = create_app(Settings(), sessions, FakeHAClient())
    with TestClient(app) as client:
        response = client.get(f"/api/cooks/{cook.id}/events")
        assert response.status_code == 200
        changed = next(item for item in response.json() if item["kind"] == "setpoint_changed")
        assert changed["ts"] == "2026-10-16T16:58:18Z"
        assert changed["elapsed_seconds"] == 75
        samples = client.get(f"/api/cooks/{cook.id}/samples").json()
        assert samples[-1]["ts"] == "2026-10-16T16:58:18Z"
        assert samples[-1]["elapsed_seconds"] == 75
