from __future__ import annotations

from pathlib import Path

import pytest
from conftest import FakeHAClient
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import create_app
from app.config import Settings
from app.models import Meat, Pellet, Spice
from app.pantry_photos import MAX_PHOTO_BYTES

JPEG = b"\xff\xd8\xff\xe0jpeg"
PNG = b"\x89PNG\r\n\x1a\npng"
WEBP = b"RIFF\x04\x00\x00\x00WEBPwebp"


def _create_item(client: TestClient, kind: str) -> int:
    payloads = {
        "pellets": {"vendor": "Oak Co", "product_name": "Oak", "price_per_pound": 1},
        "meat": {"type": "Brisket", "pounds": 10, "price_per_pound": 5},
        "spices": {"brand": "House", "name": "Pepper"},
    }
    response = client.post(f"/api/{kind}", json=payloads[kind])
    assert response.status_code == 201
    assert response.json()["has_photo"] is False
    assert response.json()["photo_url"] is None
    return int(response.json()["id"])


@pytest.mark.parametrize(
    ("kind", "contents", "media_type", "suffix"),
    [
        ("pellets", JPEG, "image/jpeg", ".jpg"),
        ("meat", PNG, "image/png", ".png"),
        ("spices", WEBP, "image/webp", ".webp"),
    ],
)
def test_upload_and_serve_each_pantry_kind(
    sessions: sessionmaker[Session],
    tmp_path: Path,
    kind: str,
    contents: bytes,
    media_type: str,
    suffix: str,
) -> None:
    photo_dir = tmp_path / "photos"
    with TestClient(
        create_app(Settings(photo_dir=str(photo_dir)), sessions, FakeHAClient())
    ) as client:
        item_id = _create_item(client, kind)
        uploaded = client.post(
            f"/api/{kind}/{item_id}/photo",
            files={"file": ("../../escape.exe", contents, "application/octet-stream")},
        )
        assert uploaded.status_code == 200
        assert uploaded.json()["has_photo"] is True
        assert uploaded.json()["photo_url"].startswith(f"/api/{kind}/{item_id}/photo?v=")
        stored = photo_dir / kind / f"{item_id}{suffix}"
        assert stored.read_bytes() == contents
        assert not (tmp_path / "escape.exe").exists()

        served = client.get(f"/api/{kind}/{item_id}/photo")
        assert served.status_code == 200
        assert served.content == contents
        assert served.headers["content-type"] == media_type
        assert served.headers["cache-control"] == "no-cache"


def test_validation_replace_and_delete_photo(
    sessions: sessionmaker[Session], tmp_path: Path
) -> None:
    photo_dir = tmp_path / "photos"
    with TestClient(
        create_app(Settings(photo_dir=str(photo_dir)), sessions, FakeHAClient())
    ) as client:
        item_id = _create_item(client, "pellets")
        url = f"/api/pellets/{item_id}/photo"
        wrong_type = client.post(
            url, files={"file": ("x.jpg", b"not an image", "image/jpeg")}
        )
        assert wrong_type.status_code == 415
        oversized = JPEG + b"x" * MAX_PHOTO_BYTES
        too_large = client.post(
            url, files={"file": ("x.jpg", oversized, "image/jpeg")}
        )
        assert too_large.status_code == 413
        assert client.post(url, files={"file": ("x.jpg", JPEG, "image/jpeg")}).status_code == 200
        old_path = photo_dir / "pellets" / f"{item_id}.jpg"
        assert old_path.exists()
        assert client.post(url, files={"file": ("x.png", PNG, "image/png")}).status_code == 200
        assert not old_path.exists()
        assert (photo_dir / "pellets" / f"{item_id}.png").exists()

        assert client.delete(url).status_code == 204
        assert client.get(url).status_code == 404
        item = client.get(f"/api/pellets/{item_id}").json()
        assert item["has_photo"] is False
        assert item["photo_url"] is None

        missing = client.post(
            "/api/pellets/9999/photo", files={"file": ("x.jpg", JPEG)}
        )
        assert missing.status_code == 404
        assert client.get("/api/pellets/9999/photo").status_code == 404
        assert client.delete("/api/pellets/9999/photo").status_code == 404


@pytest.mark.parametrize(
    ("kind", "model"), [("pellets", Pellet), ("meat", Meat), ("spices", Spice)]
)
def test_deleting_item_removes_photo(
    sessions: sessionmaker[Session],
    tmp_path: Path,
    kind: str,
    model: type[Pellet] | type[Meat] | type[Spice],
) -> None:
    photo_dir = tmp_path / "photos"
    with TestClient(
        create_app(Settings(photo_dir=str(photo_dir)), sessions, FakeHAClient())
    ) as client:
        item_id = _create_item(client, kind)
        assert client.post(
            f"/api/{kind}/{item_id}/photo", files={"file": ("x.jpg", JPEG)}
        ).status_code == 200
        with sessions() as session:
            item = session.get(model, item_id)
            assert item is not None and item.photo_path is not None
            path = Path(item.photo_path)
        assert client.delete(f"/api/{kind}/{item_id}").status_code == 204
        assert not path.exists()
