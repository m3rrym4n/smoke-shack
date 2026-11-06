from __future__ import annotations

import errno
import hashlib
import io
import json
import os
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
    archive = _archive_bytes(
        build_backup(source_db, source_photos, tmp_path / "source-showcase", "test")
    )

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


def test_restore_round_trip_includes_showcase_images(tmp_path: Path, monkeypatch) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_db = source_root / "smoke.db"
    source_photos = source_root / "photos"
    source_showcase = source_root / "showcase"
    source_showcase.mkdir()
    (source_showcase / "logo.png").write_bytes(b"logo-bytes")
    (source_showcase / "photo.jpg").write_bytes(b"photo-bytes")
    _migrate(source_db)
    archive = _archive_bytes(build_backup(source_db, source_photos, source_showcase, "test"))

    live_root = tmp_path / "live"
    live_root.mkdir()
    live_db = live_root / "smoke.db"
    live_photos = live_root / "photos"
    _migrate(live_db)

    with _client(live_db, live_photos, monkeypatch) as client:
        response = client.post("/api/restore", files={"file": ("backup.zip", archive)})

    assert response.status_code == 200, response.text
    assert (live_root / "showcase" / "logo.png").read_bytes() == b"logo-bytes"
    assert (live_root / "showcase" / "photo.jpg").read_bytes() == b"photo-bytes"


def test_old_backup_leaves_existing_showcase_untouched(tmp_path: Path, monkeypatch) -> None:
    source_db = tmp_path / "source.db"
    _migrate(source_db)
    archive = _archive_bytes(
        build_backup(source_db, tmp_path / "source-photos", tmp_path / "source-showcase", "test")
    )
    archive = _rewrite_archive(
        archive,
        lambda entries: entries.__setitem__(
            "manifest.json",
            json.dumps(
                {
                    key: value
                    for key, value in json.loads(entries["manifest.json"]).items()
                    if key != "showcase_count"
                }
            ).encode(),
        ),
    )

    live_root = tmp_path / "live-old"
    live_root.mkdir()
    live_db = live_root / "smoke.db"
    live_photos = live_root / "photos"
    live_showcase = live_root / "showcase"
    live_showcase.mkdir()
    (live_showcase / "logo.png").write_bytes(b"keep-logo")
    (live_showcase / "photo.jpg").write_bytes(b"keep-photo")
    _migrate(live_db)

    with _client(live_db, live_photos, monkeypatch) as client:
        response = client.post("/api/restore", files={"file": ("old.zip", archive)})

    assert response.status_code == 200, response.text
    assert (live_showcase / "logo.png").read_bytes() == b"keep-logo"
    assert (live_showcase / "photo.jpg").read_bytes() == b"keep-photo"


def test_invalid_showcase_entries_leave_current_data_unchanged(tmp_path: Path, monkeypatch) -> None:
    source_db = tmp_path / "source-invalid.db"
    _migrate(source_db)
    valid = _archive_bytes(
        build_backup(source_db, tmp_path / "source-invalid-photos", tmp_path / "missing", "test")
    )

    for name in ("showcase/../evil.png", "showcase/other.txt"):
        archive = _rewrite_archive(
            valid, lambda entries, name=name: entries.__setitem__(name, b"evil")
        )
        live_root = tmp_path / name.replace("/", "-").replace(".", "_")
        live_root.mkdir()
        live_db = live_root / "smoke.db"
        live_photos = live_root / "photos"
        live_showcase = live_root / "showcase"
        live_showcase.mkdir()
        (live_showcase / "logo.png").write_bytes(b"keep")
        _migrate(live_db)

        with _client(live_db, live_photos, monkeypatch) as client:
            response = client.post("/api/restore", files={"file": ("bad.zip", archive)})

        assert response.status_code == 422, (name, response.text)
        assert (live_showcase / "logo.png").read_bytes() == b"keep"


def test_restore_safety_copy_succeeds_across_filesystems(tmp_path: Path, monkeypatch) -> None:
    source_db = tmp_path / "source.db"
    _migrate(source_db)
    archive = _archive_bytes(
        build_backup(
            source_db,
            tmp_path / "source-photos",
            tmp_path / "source-showcase",
            "test",
        )
    )

    live_db = tmp_path / "live" / "smoke.db"
    live_db.parent.mkdir()
    _migrate(live_db)

    def cross_device_replace(_source: Path, _destination: Path) -> None:
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(os, "replace", cross_device_replace)

    with _client(live_db, tmp_path / "live-photos", monkeypatch) as client:
        response = client.post("/api/restore", files={"file": ("backup.zip", archive)})

    assert response.status_code == 200, response.text
    safety_path = live_db.parent / response.json()["safety_copy"]
    assert safety_path.is_file()


def test_restore_rejections_leave_current_data_unchanged(tmp_path: Path, monkeypatch) -> None:
    source_db = tmp_path / "source.db"
    _migrate(source_db)
    valid = _archive_bytes(
        build_backup(source_db, tmp_path / "none", tmp_path / "none-showcase", "test")
    )
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
    archive = _archive_bytes(
        build_backup(database, tmp_path / "photos", tmp_path / "showcase", "test")
    )
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
    with sqlite3.connect(old_db) as connection:
        connection.execute(
            "INSERT INTO pellets (id,vendor,product_name,price_per_pound,purchased_on) "
            "VALUES (3,'Legacy','Oak',1.5,'2026-10-15')"
        )
        connection.execute(
            "INSERT INTO cooks "
            "(started_at, status, pellet_id, rotisserie, has_gap, incomplete, "
            "created_at, updated_at) "
            "VALUES ('2026-10-16T16:57:03Z', 'closed', 3, 0, 0, 0, "
            "'2026-10-16T16:57:03Z', '2026-10-16T16:57:03Z')"
        )
        connection.execute(
            "INSERT INTO samples (cook_id, ts, pit_temp, setpoint, probe1, extra_probes) "
            "VALUES (last_insert_rowid(), '2026-10-16T16:58:03Z', 225, 250, 180, "
            "'{\"sensor.backup_probe\": 155}')"
        )
    archive = _archive_bytes(
        build_backup(old_db, tmp_path / "old-photos", tmp_path / "old-showcase", "old")
    )
    live_db = tmp_path / "live.db"
    _migrate(live_db)
    with _client(live_db, tmp_path / "new-photos", monkeypatch) as client:
        response = client.post("/api/restore", files={"file": ("x.zip", archive)})
    assert response.status_code == 200, response.text
    assert response.json()["schema_revision_before"] == "ef36b629902e"
    assert response.json()["schema_revision_after"] != "ef36b629902e"
    with sqlite3.connect(live_db) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(fuel)")}
        assert {"type", "upc", "bag_size_lb", "emptied_on"} <= columns
        emptied_count = connection.execute(
            "SELECT COUNT(*) FROM fuel WHERE emptied_on IS NOT NULL"
        ).fetchone()[0]
        assert emptied_count == 0
        assert connection.execute("SELECT id,type FROM fuel").fetchone() == (3, "pellets")
        assert connection.execute("SELECT fuel_id FROM cooks").fetchone() == (3,)
        readings = connection.execute(
            "SELECT channels.key, channel_readings.value, channel_readings.target "
            "FROM channel_readings JOIN channels ON channels.id = channel_readings.channel_id "
            "ORDER BY channels.key"
        ).fetchall()
        assert readings == [
            ("backup_probe", 155.0, None),
            ("pit", 225.0, 250.0),
            ("probe1", 180.0, None),
        ]
