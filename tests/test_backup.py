from __future__ import annotations

import hashlib
import io
import json
import re
import sqlite3
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

import app.api
from app.backup import build_backup
from app.config import Settings


def _database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE alembic_version (version_num TEXT NOT NULL)")
    connection.execute("INSERT INTO alembic_version VALUES ('abc123')")
    connection.execute("CREATE TABLE cooks (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    connection.execute("INSERT INTO cooks (name) VALUES ('brisket')")
    connection.commit()
    return connection


def test_build_backup_contains_valid_snapshot_manifest_and_photos(tmp_path: Path) -> None:
    database = tmp_path / "live.db"
    source = _database(database)
    source.execute("INSERT INTO cooks (name) VALUES ('just written')")
    source.commit()
    photos = tmp_path / "photos"
    (photos / "nested").mkdir(parents=True)
    (photos / "nested" / "cook.jpg").write_bytes(b"photo")
    showcase = tmp_path / "showcase"
    showcase.mkdir()
    (showcase / "logo.png").write_bytes(b"logo")
    (showcase / "photo.jpg").write_bytes(b"grill")

    archive_path = build_backup(
        database,
        photos,
        showcase,
        "2.3.0-dev.4",
        created_at=datetime(2026, 10, 31, 18, 0, tzinfo=UTC),
    )
    source.close()
    try:
        with zipfile.ZipFile(archive_path) as archive:
            assert set(archive.namelist()) == {
                "manifest.json",
                "smoke-shack.db",
                "photos/nested/cook.jpg",
                "showcase/logo.png",
                "showcase/photo.jpg",
            }
            manifest = json.loads(archive.read("manifest.json"))
            snapshot = archive.read("smoke-shack.db")

        assert manifest == {
            "format_version": 1,
            "app_version": "2.3.0-dev.4",
            "schema_revision": "abc123",
            "created_at": "2026-10-31T18:00:00Z",
            "tables": {"alembic_version": 1, "cooks": 2},
            "photo_count": 1,
            "showcase_count": 2,
            "db_sha256": hashlib.sha256(snapshot).hexdigest(),
        }
        snapshot_path = tmp_path / "snapshot.db"
        snapshot_path.write_bytes(snapshot)
        with sqlite3.connect(snapshot_path) as connection:
            assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert connection.execute("SELECT name FROM cooks ORDER BY id").fetchall() == [
                ("brisket",),
                ("just written",),
            ]
    finally:
        archive_path.unlink(missing_ok=True)


def test_build_backup_allows_missing_photo_directory(tmp_path: Path) -> None:
    database = tmp_path / "live.db"
    _database(database).close()

    archive_path = build_backup(
        database, tmp_path / "missing", tmp_path / "missing-showcase", "dev"
    )
    try:
        with zipfile.ZipFile(archive_path) as archive:
            assert archive.namelist() == ["smoke-shack.db", "manifest.json"]
            assert json.loads(archive.read("manifest.json"))["photo_count"] == 0
            assert json.loads(archive.read("manifest.json"))["showcase_count"] == 0
    finally:
        archive_path.unlink(missing_ok=True)


def test_backup_endpoint_returns_download_without_secrets(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "live.db"
    _database(database).close()
    photos = tmp_path / "photos"
    photos.mkdir()
    (photos / "cook.jpg").write_bytes(b"photo")
    build_info = tmp_path / "build_info.txt"
    build_info.write_text("4.5.6\n", encoding="utf-8")
    monkeypatch.setattr(app.api, "BUILD_INFO_PATH", build_info)
    monkeypatch.setattr(app.api, "seed_spices", lambda _sessions: None)
    settings = Settings(
        database_path=str(database),
        photo_dir=str(photos),
        ha_token="secret-token",
    )

    with TestClient(app.api.create_app(settings)) as client:
        response = client.get("/api/backup")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert re.fullmatch(
        'attachment; filename="smoke-shack-backup-\\d{8}-\\d{6}\\.zip"',
        response.headers["content-disposition"],
    )
    assert b"secret-token" not in response.content
    assert b"http://secret-ha" not in response.content
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert "config/entities.yaml" not in archive.namelist()
        assert archive.read("manifest.json")
