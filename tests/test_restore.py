from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient

import app.api
from app.backup import build_backup
from app.config import Settings


def _migrate(path: Path, revision: str = "head") -> None:
    config = Config("alembic.ini")
    config.attributes["database_path"] = str(path)
    command.upgrade(config, revision)


def _client(database: Path, photos: Path, monkeypatch, *, limit: int = 500_000_000) -> TestClient:
    monkeypatch.setattr(app.api, "seed_spices", lambda _sessions: None)
    return TestClient(
        app.api.create_app(
            Settings(
                database_path=str(database),
                photo_dir=str(photos),
                restore_max_bytes=limit,
            )
        )
    )


def _archive_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    path.unlink()
    return data


def _rewrite_archive(data: bytes, mutate) -> bytes:
    source = zipfile.ZipFile(io.BytesIO(data))
    output = io.BytesIO()
    with source, zipfile.ZipFile(output, "w") as target:
        entries = {name: source.read(name) for name in source.namelist()}
        mutate(entries)
        for name, content in entries.items():
            target.writestr(name, content)
    return output.getvalue()


def test_restore_round_trip_rewrites_paths_and_creates_safety_copy(
    tmp_path: Path, monkeypatch
) -> None:
    source_db = tmp_path / "source.db"
    source_photos = tmp_path / "old-photos"
    _migrate(source_db)
    cook_photo = source_photos / "1" / "cook.jpg"
    meat_photo = source_photos / "meat" / "1.jpg"
    cook_photo.parent.mkdir(parents=True)
    meat_photo.parent.mkdir(parents=True)
    cook_photo.write_bytes(b"cook-photo")
    meat_photo.write_bytes(b"meat-photo")
    now = "2026-10-31T12:00:00Z"
    with sqlite3.connect(source_db) as connection:
        connection.execute(
            "INSERT INTO meat "
            "(id,type,pounds,price_per_pound,store,purchased_on,photo_path,cooked) "
            "VALUES (1,'Brisket',10,5,'Shop',?,?,0)",
            (date(2026, 10, 30).isoformat(), str(meat_photo)),
        )
        connection.execute(
            "INSERT INTO cooks "
            "(id,started_at,status,rotisserie,has_gap,incomplete,created_at,updated_at,"
            "exclude_from_stats) VALUES (1,?,'complete',0,0,0,?,?,0)",
            (now, now, now),
        )
        connection.execute(
            "INSERT INTO events "
            "(id,cook_id,ts,kind,source,title,data,photo_path) "
            "VALUES (1,1,?,'custom','user','Photo','{}',?)",
            (now, str(cook_photo)),
        )
        connection.execute(
            "INSERT INTO photos (id,cook_id,event_id,path) VALUES (1,1,1,?)",
            (str(cook_photo),),
        )
        connection.commit()
    archive = _archive_bytes(build_backup(source_db, source_photos, "test"))

    live_db = tmp_path / "live" / "smoke.db"
    live_db.parent.mkdir()
    live_photos = tmp_path / "new-photos"
    live_photos.mkdir()
    (live_photos / "obsolete.jpg").write_bytes(b"old")
    _migrate(live_db)
    with sqlite3.connect(live_db) as connection:
        connection.execute(
            "INSERT INTO notes (body,title,scope,created_at) VALUES ('old','old','gear',?)",
            (now,),
        )
        connection.commit()

    with _client(live_db, live_photos, monkeypatch) as client:
        response = client.post(
            "/api/restore", files={"file": ("backup.zip", archive, "application/zip")}
        )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["tables"]["cooks"] == 1
    assert result["photo_count"] == 2
    assert result["schema_revision_before"] == result["schema_revision_after"]
    assert (live_db.parent / result["safety_copy"]).is_file()
    assert not (live_photos / "obsolete.jpg").exists()
    assert (live_photos / "1" / "cook.jpg").read_bytes() == b"cook-photo"
    with sqlite3.connect(live_db) as connection:
        assert connection.execute("SELECT path FROM photos").fetchone() == (
            str(live_photos / "1" / "cook.jpg"),
        )
        assert connection.execute("SELECT photo_path FROM events").fetchone() == (
            str(live_photos / "1" / "cook.jpg"),
        )
        assert connection.execute("SELECT photo_path FROM meat").fetchone() == (
            str(live_photos / "meat" / "1.jpg"),
        )


def test_restore_rejections_leave_current_data_unchanged(tmp_path: Path, monkeypatch) -> None:
    source_db = tmp_path / "source.db"
    _migrate(source_db)
    valid = _archive_bytes(build_backup(source_db, tmp_path / "none", "test"))
    head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()

    cases = {
        "zip-slip": _rewrite_archive(
            valid, lambda entries: entries.__setitem__("photos/../x", b"x")
        ),
        "checksum": _rewrite_archive(
            valid,
            lambda entries: entries.__setitem__(
                "manifest.json",
                json.dumps({**json.loads(entries["manifest.json"]), "db_sha256": "bad"}).encode(),
            ),
        ),
        "newer": _rewrite_archive(
            valid,
            lambda entries: entries.__setitem__(
                "manifest.json",
                json.dumps(
                    {**json.loads(entries["manifest.json"]), "schema_revision": f"{head}-future"}
                ).encode(),
            ),
        ),
        "corrupt": _rewrite_archive(
            valid,
            lambda entries: (
                entries.__setitem__("smoke-shack.db", b"not sqlite"),
                entries.__setitem__(
                    "manifest.json",
                    json.dumps(
                        {
                            **json.loads(entries["manifest.json"]),
                            "db_sha256": hashlib.sha256(b"not sqlite").hexdigest(),
                        }
                    ).encode(),
                ),
            ),
        ),
    }
    for name, archive in cases.items():
        live_db = tmp_path / f"{name}.db"
        _migrate(live_db)
        with sqlite3.connect(live_db) as connection:
            connection.execute(
                "INSERT INTO notes (body,title,scope,created_at) VALUES ('keep','keep','gear',?)",
                (datetime.now(UTC).isoformat(),),
            )
            connection.commit()
        with _client(live_db, tmp_path / f"{name}-photos", monkeypatch) as client:
            response = client.post("/api/restore", files={"file": ("x.zip", archive)})
        assert response.status_code in {409, 422}, (name, response.text)
        with sqlite3.connect(live_db) as connection:
            assert connection.execute("SELECT body FROM notes").fetchall() == [("keep",)]


def test_restore_rejects_active_cook_and_oversized_upload(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "live.db"
    _migrate(database)
    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO cooks "
            "(started_at,status,rotisserie,has_gap,incomplete,created_at,updated_at,"
            "exclude_from_stats) "
            "VALUES (?,'cook',0,0,0,?,?,0)",
            (now, now, now),
        )
        connection.commit()
    archive = _archive_bytes(build_backup(database, tmp_path / "photos", "test"))
    with _client(database, tmp_path / "photos", monkeypatch) as client:
        response = client.post("/api/restore", files={"file": ("x.zip", archive)})
    assert response.status_code == 409
    assert response.json()["detail"] == "Finish or end the active cook before restoring"

    with _client(database, tmp_path / "photos", monkeypatch, limit=10) as client:
        response = client.post("/api/restore", files={"file": ("x.zip", archive)})
    assert response.status_code == 413


def test_restore_migrates_older_revision(tmp_path: Path, monkeypatch) -> None:
    old_db = tmp_path / "old.db"
    _migrate(old_db, "ef36b629902e")
    archive = _archive_bytes(build_backup(old_db, tmp_path / "old-photos", "old"))
    live_db = tmp_path / "live.db"
    _migrate(live_db)
    with _client(live_db, tmp_path / "new-photos", monkeypatch) as client:
        response = client.post("/api/restore", files={"file": ("x.zip", archive)})
    assert response.status_code == 200, response.text
    assert response.json()["schema_revision_before"] == "ef36b629902e"
    assert response.json()["schema_revision_after"] != "ef36b629902e"
