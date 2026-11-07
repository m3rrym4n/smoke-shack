from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import FakeClock, FakeHAClient, add_channels
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api import create_app
from app.config import Settings
from app.ha import HAStatus
from app.models import Cook, Equipment, Event
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
        assert "<title>Smoke-Shack</title>" in home.text
        assert "SMOKE-SHACK" in home.text
        assert "LOW &amp; SLOW" in home.text
        assert "PELLET-FIRED" not in home.text
        assert client.get("/health").status_code == 200
        assert client.get("/docs").status_code == 200


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, '<base href="/">'),
        ("/api/hassio_ingress/abc123", '<base href="/api/hassio_ingress/abc123/">'),
        ('/api/hassio_ingress/abc"123', '<base href="/">'),
        ("/api/hassio_ingress/<abc>", '<base href="/">'),
        ("/api/hassio_ingress/abc/extra", '<base href="/">'),
    ],
)
def test_static_shell_uses_only_valid_ingress_base(
    sessions: sessionmaker[Session], header: str | None, expected: str
) -> None:
    headers = {"X-Ingress-Path": header} if header is not None else {}
    with TestClient(create_app(Settings(), sessions, FakeHAClient())) as client:
        response = client.get("/", headers=headers)

    assert response.status_code == 200
    assert expected in response.text
    if header is not None and expected == '<base href="/">':
        assert header not in response.text


def test_api_routes_remain_at_normal_paths(sessions: sessionmaker[Session]) -> None:
    with TestClient(create_app(Settings(), sessions, FakeHAClient())) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/status").status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/status",
        "/api/cooks?limit=100&offset=0&state=planned",
    ],
)
def test_repeated_leading_slashes_match_normal_paths(
    sessions: sessionmaker[Session], path: str
) -> None:
    with TestClient(create_app(Settings(), sessions, FakeHAClient())) as client:
        normal = client.get(path)
        repeated = client.get(f"http://testserver/{path}")

    assert repeated.status_code == normal.status_code
    assert repeated.content == normal.content


def test_only_leading_slashes_are_collapsed(sessions: sessionmaker[Session]) -> None:
    with TestClient(create_app(Settings(), sessions, FakeHAClient())) as client:
        normal = client.get("/status")
        internal = client.get("/api//cooks")

    assert normal.status_code == 200
    assert internal.status_code == 404


def test_frontend_has_no_root_relative_resources_or_direct_fetches() -> None:
    static = Path("app/static")
    index = (static / "index.html").read_text(encoding="utf-8")
    javascript = {
        path: path.read_text(encoding="utf-8")
        for path in (static / "js").rglob("*.js")
        if "vendor" not in path.parts
    }

    assert 'href="/' not in index
    assert 'src="/' not in index
    for path, source in javascript.items():
        assert 'href="/' not in source, path
        assert 'src="/' not in source, path
        if path.name != "api.js":
            assert "fetch(" not in source, path


def test_static_files_revalidate_without_changing_api_cache(
    sessions: sessionmaker[Session],
) -> None:
    app = create_app(Settings(), sessions, FakeHAClient())
    with TestClient(app) as client:
        for path in ("/", "/js/app.js", "/css/signage.css"):
            response = client.get(path)
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-cache"
            assert response.headers["etag"]
            assert response.headers["last-modified"]

            revalidated = client.get(path, headers={"If-None-Match": response.headers["etag"]})
            assert revalidated.status_code == 304
            assert revalidated.headers["cache-control"] == "no-cache"

        health = client.get("/health")
        assert "cache-control" not in health.headers


def test_live_view_static_assets_exist(sessions: sessionmaker[Session]) -> None:
    app = create_app(Settings(), sessions, FakeHAClient())
    with TestClient(app) as client:
        for path in (
            "/js/views/live.js",
            "/js/components/gauge.js",
            "/js/components/showcase.js",
            "/js/components/smoke.js",
            "/js/live-logic.js",
            "/js/smoke-logic.js",
        ):
            response = client.get(path)
            assert response.status_code == 200
            assert "javascript" in response.headers["content-type"]


def test_meat_view_static_assets_exist(sessions: sessionmaker[Session]) -> None:
    app = create_app(Settings(), sessions, FakeHAClient())
    with TestClient(app) as client:
        for path in ("/js/views/meat.js", "/js/meat-logic.js", "/js/components/ui.js"):
            response = client.get(path)
            assert response.status_code == 200
            assert "javascript" in response.headers["content-type"]


def test_pellet_view_static_assets_exist(sessions: sessionmaker[Session]) -> None:
    app = create_app(Settings(), sessions, FakeHAClient())
    with TestClient(app) as client:
        for path in ("/js/views/pellets.js", "/js/pellets-logic.js"):
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
    assert status["ingest"]["data_gap_event_min_seconds"] == 120
    assert status["version"] == "dev"
    assert status["grill_name"] == "Grill"
    assert status["grill_title"] == "Grill"
    assert status["grill_maker"] is None
    assert status["channels"] == []


def test_status_lists_connected_grill_channels_in_order(
    sessions: sessionmaker[Session],
) -> None:
    add_channels(sessions, ("pit", "probe1", "probe2", "probe3", "probe4"))

    with TestClient(create_app(Settings(), sessions)) as client:
        channels = client.get("/status").json()["channels"]

    assert [channel["key"] for channel in channels] == [
        "pit", "probe1", "probe2", "probe3", "probe4"
    ]
    assert [channel["role"] for channel in channels] == [
        "pit", "meat", "meat", "meat", "meat"
    ]


def test_status_with_supervisor_configured(sessions: sessionmaker[Session]) -> None:
    app = create_app(Settings(supervisor_token="supervisor-secret"), sessions)
    with TestClient(app) as client:
        status = client.get("/status").json()

    assert status["ha"]["configured"] is True
    assert "supervisor-secret" not in repr(status)


def test_status_grill_name_fallback_and_cached_ha_name(
    sessions: sessionmaker[Session],
) -> None:
    fake = FakeHAClient()
    app = create_app(Settings(grill_name="Backyard grill"), sessions, fake)
    with TestClient(app) as client:
        assert client.get("/status").json()["grill_name"] == "Grill"
        fake.status.grill_name = "Daniel Boone"
        fake.status.connected = False
        status = client.get("/status").json()
        assert status["grill_name"] == "Grill"
        assert status["grill_title"] == "Grill"
        fake.status.grill_title = "Backyard Beast"
        fake.status.grill_maker = "Green Mountain Grills"
        status = client.get("/status").json()
        assert status["grill_name"] == "Grill"
        assert status["grill_title"] == "Grill"
        assert status["grill_maker"] is None


def test_status_does_not_report_planned_cook(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        session.add(Cook(started_at=None, status="planned"))
        session.commit()

    with TestClient(create_app(Settings(), sessions)) as client:
        assert client.get("/status").json()["active_cook"] is None


def test_status_uses_connected_equipment_identity_and_pictures(
    sessions: sessionmaker[Session], tmp_path: Path
) -> None:
    photo = tmp_path / "grill.jpg"
    logo = tmp_path / "logo.png"
    photo.write_bytes(b"photo")
    logo.write_bytes(b"logo")
    with sessions() as session:
        grill = session.scalar(select(Equipment).where(Equipment.connected.is_(True)))
        assert grill is not None
        grill.nickname = "Patio Grill"
        grill.maker = "Masterbuilt"
        grill.model = "Gravity Series 800"
        grill.photo_path = str(photo)
        grill.logo_path = str(logo)
        session.commit()

    app = create_app(Settings(), sessions)
    with TestClient(app) as client:
        status = client.get("/status").json()

    assert status["grill_title"] == "Gravity Series 800"
    assert status["grill_maker"] == "Masterbuilt"
    assert status["photo_url"] == "/api/equipment/1/photo"
    assert status["logo_url"] == "/api/equipment/1/logo"
    assert "My grill" not in status.values()


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

    assert (
        "HA_URL/HA_TOKEN or SUPERVISOR_TOKEN not set; Home Assistant ingest disabled"
        in caplog.messages
    )


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


def test_events_api_still_returns_data_gap_events(
    sessions: sessionmaker[Session], clock: FakeClock
) -> None:
    service = CookService(sessions, clock)
    cook = service.process(
        GrillSnapshot(setpoint=150, fire_state="Startup", power_state="On", hvac_mode="heat")
    )
    assert cook is not None
    with sessions() as session:
        session.add(
            Event(
                cook_id=cook.id,
                ts=clock.now(),
                kind="data_gap",
                source="auto",
                title="Home Assistant data gap",
                description=None,
                data={"start": clock.now().isoformat(), "end": clock.now().isoformat()},
            )
        )
        session.commit()

    app = create_app(Settings(), sessions, FakeHAClient())
    with TestClient(app) as client:
        response = client.get(f"/api/cooks/{cook.id}/events")

    assert response.status_code == 200
    assert any(event["kind"] == "data_gap" for event in response.json())
