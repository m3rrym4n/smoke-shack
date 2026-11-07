from pathlib import Path

import pytest
from conftest import FakeHAClient
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import create_app
from app.config import Settings
from app.pantry_photos import MAX_PHOTO_BYTES

JPEG = b"\xff\xd8\xff\xe0jpeg"
PNG = b"\x89PNG\r\n\x1a\npng"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>'
PNG_WITH_SVG_METADATA = PNG + b'<metadata value="<svg" />'


@pytest.mark.parametrize(
    ("kind", "first", "second", "content_type"),
    [
        ("photo", JPEG, PNG, "image/png"),
        ("logo", PNG, SVG, "image/svg+xml"),
    ],
)
def test_upload_replace_serve_and_remove_equipment_images(
    sessions: sessionmaker[Session],
    tmp_path: Path,
    kind: str,
    first: bytes,
    second: bytes,
    content_type: str,
) -> None:
    photo_dir = tmp_path / "photos"
    app = create_app(Settings(photo_dir=str(photo_dir)), sessions, FakeHAClient())
    with TestClient(app) as client:
        initial = client.get("/api/equipment/1")
        assert initial.status_code == 200
        assert initial.json()[f"has_{kind}"] is False
        assert initial.json()[f"{kind}_url"] is None

        url = f"/api/equipment/1/{kind}"
        uploaded = client.post(url, files={"file": ("first.bin", first)})
        assert uploaded.status_code == 200, uploaded.text
        assert uploaded.json()[f"has_{kind}"] is True
        assert uploaded.json()[f"{kind}_url"] == url
        assert client.post(url, files={"file": ("second.bin", second)}).status_code == 200

        served = client.get(url)
        assert served.status_code == 200
        assert served.content == second
        assert served.headers["content-type"] == content_type
        assert served.headers["cache-control"] == "no-cache"

        assert client.delete(url).status_code == 204
        assert client.get(url).status_code == 404
        response = client.get("/api/equipment/1").json()
        assert response[f"has_{kind}"] is False
        assert response[f"{kind}_url"] is None


@pytest.mark.parametrize("kind", ["photo", "logo"])
def test_equipment_image_validation_and_missing_equipment(
    sessions: sessionmaker[Session], tmp_path: Path, kind: str
) -> None:
    app = create_app(Settings(photo_dir=str(tmp_path / "photos")), sessions, FakeHAClient())
    with TestClient(app) as client:
        url = f"/api/equipment/1/{kind}"
        assert client.post(url, files={"file": ("bad.txt", b"not an image")}).status_code == 415
        oversized = JPEG + b"x" * MAX_PHOTO_BYTES
        assert client.post(url, files={"file": ("large.jpg", oversized)}).status_code == 413
        missing = f"/api/equipment/999/{kind}"
        assert client.post(missing, files={"file": ("x.jpg", JPEG)}).status_code == 404
        assert client.get(missing).status_code == 404
        assert client.delete(missing).status_code == 404


def test_equipment_logo_uses_photo_signature_before_svg_metadata(
    sessions: sessionmaker[Session], tmp_path: Path
) -> None:
    photo_dir = tmp_path / "photos"
    app = create_app(Settings(photo_dir=str(photo_dir)), sessions, FakeHAClient())
    with TestClient(app) as client:
        response = client.post(
            "/api/equipment/1/logo",
            files={"file": ("logo.png", PNG_WITH_SVG_METADATA, "image/png")},
        )
        served = client.get("/api/equipment/1/logo")

    assert response.status_code == 200
    assert served.content == PNG_WITH_SVG_METADATA
    assert served.headers["content-type"] == "image/png"
    assert (photo_dir / "equipment" / "1" / "logo.png").read_bytes() == PNG_WITH_SVG_METADATA


def test_equipment_logo_rejects_invalid_utf8_svg_and_unsupported_file(
    sessions: sessionmaker[Session], tmp_path: Path
) -> None:
    app = create_app(Settings(photo_dir=str(tmp_path / "photos")), sessions, FakeHAClient())
    with TestClient(app) as client:
        invalid_svg = client.post(
            "/api/equipment/1/logo",
            files={"file": ("logo.svg", b"<svg>\xff</svg>", "image/svg+xml")},
        )
        unsupported = client.post(
            "/api/equipment/1/logo",
            files={"file": ("logo.bin", b"not an image", "application/octet-stream")},
        )

    assert invalid_svg.status_code == 422
    assert invalid_svg.json()["detail"] == "SVG must be valid UTF-8 text"
    assert unsupported.status_code == 415
    assert unsupported.json()["detail"] == "Unsupported image type"
