from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import create_app
from app.config import Settings

PNG = b"\x89PNG\r\n\x1a\n" + b"png data"
JPEG = b"\xff\xd8\xff\xe0" + b"jpeg data"
WEBP = b"RIFF\x0c\x00\x00\x00WEBP" + b"webp data"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><path fill="#fff" d="M0 0h10v10z"/></svg>'
PNG_WITH_SVG_METADATA = PNG + b'<metadata value="<svg" />'


def test_showcase_upload_replace_serve_delete_and_persist(
    tmp_path: Path, sessions: sessionmaker[Session]
) -> None:
    photo_dir = tmp_path / "photos"
    settings = Settings(photo_dir=str(photo_dir))

    with TestClient(create_app(settings, sessions)) as client:
        assert client.get("/api/showcase").json() == {"logo_url": None, "photo_url": None}

        uploaded = client.put(
            "/api/showcase/logo",
            files={"file": ("logo.txt", PNG, "text/plain")},
        )
        assert uploaded.status_code == 200
        assert uploaded.json() == {"logo_url": "/api/showcase/logo"}
        first = client.get("/api/showcase/logo")
        assert first.content == PNG
        assert first.headers["content-type"] == "image/png"
        assert first.headers["x-content-type-options"] == "nosniff"
        assert first.headers["cache-control"] == "no-cache"
        assert first.headers["etag"]
        revalidated = client.get(
            "/api/showcase/logo", headers={"If-None-Match": first.headers["etag"]}
        )
        assert revalidated.status_code == 304

        replaced = client.put(
            "/api/showcase/logo",
            files={"file": ("logo.jpg", JPEG, "image/jpeg")},
        )
        assert replaced.status_code == 200
        served = client.get("/api/showcase/logo")
        assert served.content == JPEG
        assert served.headers["content-type"] == "image/jpeg"

        assert (
            client.put(
                "/api/showcase/photo",
                files={"file": ("grill.webp", WEBP, "image/webp")},
            ).status_code
            == 200
        )
        assert client.get("/api/showcase").json() == {
            "logo_url": "/api/showcase/logo",
            "photo_url": "/api/showcase/photo",
        }

    showcase_dir = tmp_path / "showcase"
    assert (showcase_dir / "logo.jpg").read_bytes() == JPEG
    assert (showcase_dir / "photo.webp").read_bytes() == WEBP
    assert not (showcase_dir / "logo.png").exists()

    with TestClient(create_app(settings, sessions)) as client:
        assert client.get("/api/showcase/photo").content == WEBP
        assert client.delete("/api/showcase/photo").status_code == 204
        assert client.get("/api/showcase/photo").status_code == 404
        assert client.get("/api/showcase").json()["photo_url"] is None


def test_showcase_rejects_bad_types_and_oversized_files(
    tmp_path: Path, sessions: sessionmaker[Session]
) -> None:
    settings = Settings(photo_dir=str(tmp_path / "photos"))
    with TestClient(create_app(settings, sessions)) as client:
        svg_photo = client.put(
            "/api/showcase/photo",
            files={"file": ("photo.svg", SVG, "image/svg+xml")},
        )
        renamed_text = client.put(
            "/api/showcase/photo",
            files={"file": ("photo.png", b"not really an image", "image/png")},
        )
        too_large = client.put(
            "/api/showcase/logo",
            files={"file": ("huge.png", PNG + b"x" * (5 * 1024 * 1024), "image/png")},
        )

    assert svg_photo.status_code == 422
    assert "PNG, JPEG, or WebP" in svg_photo.json()["detail"]
    assert renamed_text.status_code == 422
    assert "PNG, JPEG, or WebP" in renamed_text.json()["detail"]
    assert too_large.status_code == 422
    assert "5 MB" in too_large.json()["detail"]
    assert not (tmp_path / "showcase" / "logo.png").exists()


def test_showcase_accepts_and_serves_safe_svg_logo(
    tmp_path: Path, sessions: sessionmaker[Session]
) -> None:
    settings = Settings(photo_dir=str(tmp_path / "photos"))
    with TestClient(create_app(settings, sessions)) as client:
        uploaded = client.put(
            "/api/showcase/logo",
            files={"file": ("logo.svg", SVG, "image/svg+xml")},
        )
        served = client.get("/api/showcase/logo")

    assert uploaded.status_code == 200
    assert served.content == SVG
    assert served.headers["content-type"] == "image/svg+xml"
    assert served.headers["x-content-type-options"] == "nosniff"
    assert served.headers["content-security-policy"] == (
        "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    )
    assert (tmp_path / "showcase" / "logo.svg").read_bytes() == SVG


def test_showcase_logo_uses_photo_signature_before_svg_metadata(
    tmp_path: Path, sessions: sessionmaker[Session]
) -> None:
    settings = Settings(photo_dir=str(tmp_path / "photos"))
    with TestClient(create_app(settings, sessions)) as client:
        uploaded = client.put(
            "/api/showcase/logo",
            files={"file": ("logo.png", PNG_WITH_SVG_METADATA, "image/png")},
        )
        served = client.get("/api/showcase/logo")

    assert uploaded.status_code == 200
    assert served.content == PNG_WITH_SVG_METADATA
    assert served.headers["content-type"] == "image/png"
    assert (tmp_path / "showcase" / "logo.png").read_bytes() == PNG_WITH_SVG_METADATA


@pytest.mark.parametrize(
    ("svg", "message"),
    [
        (b"<svg><script>alert(1)</script></svg>", "script elements"),
        (b"<svg><foreignObject /></svg>", "foreignObject elements"),
        (b'<svg><a href="javascript:alert(1)" /></svg>', "javascript: URLs"),
        (b'<svg onload="alert(1)" />', "event handler attributes"),
        (b'<svg><image href="https://example.com/logo.png" /></svg>', "href references"),
        (b'<svg><use xlink:href="logo.svg#mark" /></svg>', "href references"),
        (b'<!DOCTYPE svg SYSTEM "logo.dtd"><svg />', "DOCTYPE declaration"),
        (b'<!ENTITY logo "unsafe"><svg />', "ENTITY declaration"),
    ],
)
def test_showcase_rejects_unsafe_svg_logo(
    tmp_path: Path,
    sessions: sessionmaker[Session],
    svg: bytes,
    message: str,
) -> None:
    settings = Settings(photo_dir=str(tmp_path / "photos"))
    with TestClient(create_app(settings, sessions)) as client:
        response = client.put(
            "/api/showcase/logo",
            files={"file": ("logo.svg", svg, "image/svg+xml")},
        )

    assert response.status_code == 422
    assert message in response.json()["detail"]
    assert not (tmp_path / "showcase" / "logo.svg").exists()
