from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import create_app
from app.config import Settings
from app.models import Cook, Event, Photo
from app.routes.photos import MAX_PHOTO_BYTES


def _cook() -> Cook:
    return Cook(started_at=datetime(2026, 10, 16, 16, 57, 3, tzinfo=UTC), status="cook")


def test_photo_upload_serve_list_patch_and_delete(
    sessions: sessionmaker[Session], tmp_path: Path
) -> None:
    photo_dir = tmp_path / "photos"
    with sessions() as session:
        cook = _cook()
        session.add(cook)
        session.flush()
        event = Event(
            cook_id=cook.id,
            ts=cook.started_at,
            kind="custom",
            source="user",
            title="Wrapped",
            data={},
        )
        session.add(event)
        session.commit()
        cook_id, event_id = cook.id, event.id

    with TestClient(create_app(Settings(photo_dir=str(photo_dir)), sessions)) as client:
        uploaded = client.post(
            f"/api/cooks/{cook_id}/photos",
            files={"file": ("untrusted.exe", b"png bytes", "image/png")},
            data={"caption": "Foil on", "event_id": str(event_id)},
        )
        assert uploaded.status_code == 201
        body = uploaded.json()
        assert body == {
            "id": body["id"],
            "cook_id": cook_id,
            "event_id": event_id,
            "caption": "Foil on",
            "url": f'/api/photos/{body["id"]}/file',
        }
        photo_id = body["id"]

        listed = client.get(f"/api/cooks/{cook_id}/photos")
        assert listed.json() == [body]
        served = client.get(body["url"])
        assert served.status_code == 200
        assert served.headers["content-type"] == "image/png"
        assert served.content == b"png bytes"

        patched = client.patch(f"/api/photos/{photo_id}", json={"caption": "Ready"})
        assert patched.status_code == 200
        assert patched.json()["caption"] == "Ready"

        with sessions() as session:
            photo = session.get(Photo, photo_id)
            event = session.get(Event, event_id)
            assert photo is not None
            stored_path = Path(photo.path)
            assert stored_path.parent == photo_dir / str(cook_id)
            assert stored_path.suffix == ".png"
            assert stored_path.name != "untrusted.exe"
            assert stored_path.is_file()
            assert event is not None
            assert event.photo_path == photo.path

        deleted = client.delete(f"/api/photos/{photo_id}")
        assert deleted.status_code == 204
        assert not stored_path.exists()

    with sessions() as session:
        assert session.get(Photo, photo_id) is None
        event = session.get(Event, event_id)
        assert event is not None
        assert event.photo_path is None


def test_photo_upload_validation(sessions: sessionmaker[Session], tmp_path: Path) -> None:
    with sessions() as session:
        cook = _cook()
        other_cook = _cook()
        session.add_all([cook, other_cook])
        session.flush()
        other_event = Event(
            cook_id=other_cook.id,
            ts=other_cook.started_at,
            kind="custom",
            source="user",
            title="Other",
            data={},
        )
        session.add(other_event)
        session.commit()
        cook_id, other_event_id = cook.id, other_event.id

    photo_dir = tmp_path / "photos"
    with TestClient(create_app(Settings(photo_dir=str(photo_dir)), sessions)) as client:
        missing = client.post(
            "/api/cooks/999/photos",
            files={"file": ("photo.png", b"png", "image/png")},
        )
        assert missing.status_code == 404
        assert missing.json() == {"detail": "Cook not found"}

        unsupported = client.post(
            f"/api/cooks/{cook_id}/photos",
            files={"file": ("photo.gif", b"gif", "image/gif")},
        )
        assert unsupported.status_code == 415

        oversized = client.post(
            f"/api/cooks/{cook_id}/photos",
            files={"file": ("photo.png", b"x" * (MAX_PHOTO_BYTES + 1), "image/png")},
        )
        assert oversized.status_code == 413

        wrong_event = client.post(
            f"/api/cooks/{cook_id}/photos",
            files={"file": ("photo.webp", b"webp", "image/webp")},
            data={"event_id": str(other_event_id)},
        )
        assert wrong_event.status_code == 422

    assert list(photo_dir.rglob("*")) == [photo_dir / str(cook_id)]


def test_delete_cook_removes_photo_file(
    sessions: sessionmaker[Session], tmp_path: Path
) -> None:
    photo_dir = tmp_path / "photos"
    with sessions() as session:
        cook = _cook()
        cook.ended_at = cook.started_at
        session.add(cook)
        session.commit()
        cook_id = cook.id

    with TestClient(create_app(Settings(photo_dir=str(photo_dir)), sessions)) as client:
        uploaded = client.post(
            f"/api/cooks/{cook_id}/photos",
            files={"file": ("photo.jpg", b"jpeg", "image/jpeg")},
        )
        photo_id = uploaded.json()["id"]
        with sessions() as session:
            photo = session.get(Photo, photo_id)
            assert photo is not None
            path = Path(photo.path)
        assert path.is_file()
        assert client.delete(f"/api/cooks/{cook_id}").status_code == 204
        assert not path.exists()
        assert not path.parent.exists()
