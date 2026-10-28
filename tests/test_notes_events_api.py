from __future__ import annotations

from datetime import UTC, datetime

import pytest
from conftest import FakeHAClient
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import create_app
from app.config import Settings
from app.models import Cook, Event


def _cook(sessions: sessionmaker[Session]) -> Cook:
    with sessions() as session:
        cook = Cook(started_at=datetime(2026, 10, 16, 16, 57, 3, tzinfo=UTC))
        session.add(cook)
        session.commit()
        session.refresh(cook)
        session.expunge(cook)
        return cook


def test_notes_crud_filters_and_bad_cook(sessions: sessionmaker[Session]) -> None:
    cook = _cook(sessions)
    with TestClient(create_app(Settings(), sessions, FakeHAClient())) as client:
        first = client.post(
            "/api/notes",
            json={"title": "Wrap", "body": "Use foil", "scope": "this_cook", "cook_id": cook.id},
        )
        second = client.post(
            "/api/notes", json={"title": "Pellets", "body": "Try oak", "scope": "pellets"}
        )
        assert first.status_code == second.status_code == 201
        assert first.json()["created_at"].endswith("Z")
        assert [note["id"] for note in client.get("/api/notes").json()] == [
            second.json()["id"],
            first.json()["id"],
        ]
        assert client.get("/api/notes?scope=this_cook").json() == [first.json()]
        assert client.get(f"/api/notes?cook_id={cook.id}").json() == [first.json()]
        assert client.get(f"/api/notes/{first.json()['id']}").json() == first.json()

        patched = client.patch(
            f"/api/notes/{first.json()['id']}", json={"title": "Wrapped", "cook_id": None}
        )
        assert patched.status_code == 200
        assert patched.json()["title"] == "Wrapped"
        assert patched.json()["cook_id"] is None
        assert client.delete(f"/api/notes/{second.json()['id']}").status_code == 204
        assert client.get(f"/api/notes/{second.json()['id']}").status_code == 404

        bad = client.post(
            "/api/notes",
            json={"title": "Bad", "body": "Cook", "scope": "this_cook", "cook_id": 9999},
        )
        assert bad.status_code == 422
        assert bad.json() == {"detail": "Cook not found"}


def test_user_events_create_patch_delete_and_exact_timestamp(
    sessions: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    cook = _cook(sessions)
    now = datetime(2026, 10, 16, 16, 58, 18, tzinfo=UTC)
    monkeypatch.setattr("app.routes.events.utc_now", lambda: now)
    with TestClient(create_app(Settings(), sessions, FakeHAClient())) as client:
        defaulted = client.post(f"/api/cooks/{cook.id}/events", json={"title": "The stall"})
        assert defaulted.status_code == 201
        assert defaulted.json()["ts"] == "2026-10-16T16:58:18Z"
        assert defaulted.json()["elapsed_seconds"] == 75
        assert defaulted.json()["kind"] == "custom"
        assert defaulted.json()["source"] == "user"

        explicit = client.post(
            f"/api/cooks/{cook.id}/events",
            json={
                "kind": "wrapped",
                "title": "Wrapped",
                "description": "Foil",
                "ts": "2026-10-16T17:00:03Z",
            },
        )
        assert explicit.status_code == 201
        assert explicit.json()["elapsed_seconds"] == 180
        assert explicit.json()["description"] == "Foil"
        assert explicit.json()["kind"] == "wrapped"

        patched = client.patch(
            f"/api/events/{explicit.json()['id']}",
            json={"kind": "rested", "title": "Wrapped tight", "ts": "2026-10-16T17:01:03Z"},
        )
        assert patched.status_code == 200
        assert patched.json()["title"] == "Wrapped tight"
        assert patched.json()["kind"] == "rested"
        assert patched.json()["elapsed_seconds"] == 240
        listed = client.get(f"/api/cooks/{cook.id}/events").json()
        assert [row["id"] for row in listed] == [defaulted.json()["id"], explicit.json()["id"]]
        assert client.delete(f"/api/events/{explicit.json()['id']}").status_code == 204


def test_event_time_before_start_and_automatic_events_are_read_only(
    sessions: sessionmaker[Session],
) -> None:
    cook = _cook(sessions)
    with sessions() as session:
        automatic = Event(
            cook_id=cook.id,
            ts=cook.started_at,
            kind="fire_lit",
            source="auto",
            title="Fire lit",
        )
        session.add(automatic)
        session.commit()
        automatic_id = automatic.id

    with TestClient(create_app(Settings(), sessions, FakeHAClient())) as client:
        too_early = client.post(
            f"/api/cooks/{cook.id}/events",
            json={"title": "Early", "ts": "2026-10-16T16:57:02Z"},
        )
        assert too_early.status_code == 422
        assert too_early.json() == {"detail": "Event timestamp cannot be before cook start"}
        for response in (
            client.patch(f"/api/events/{automatic_id}", json={"title": "Changed"}),
            client.delete(f"/api/events/{automatic_id}"),
        ):
            assert response.status_code == 409
            assert response.json() == {"detail": "Automatic events are read-only"}
