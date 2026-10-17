from __future__ import annotations

from datetime import UTC, datetime

from conftest import FakeClock, FakeHAClient
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import create_app
from app.config import Settings
from app.service import CookService, GrillSnapshot


def test_health(sessions: sessionmaker[Session]) -> None:
    app = create_app(Settings(), sessions, FakeHAClient())
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}


def test_exact_timestamp_and_elapsed_seconds(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    service = CookService(sessions, clock)
    cook = service.process(
        GrillSnapshot(setpoint=150, fire_state="on", power_state="on", hvac_mode="heat")
    )
    assert cook is not None
    clock.advance(seconds=75)
    event_time = datetime(2026, 10, 16, 16, 58, 18, tzinfo=UTC)
    service.process(
        GrillSnapshot(setpoint=275, fire_state="on", power_state="on", hvac_mode="heat"),
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
