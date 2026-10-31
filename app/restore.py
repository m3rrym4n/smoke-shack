from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.backup import _database_manifest, build_backup
from app.models import Cook

ALLOWED_FILES = {"manifest.json", "smoke-shack.db"}


async def restore_backup(
    upload: UploadFile,
    database_path: Path,
    photo_dir: Path,
    sessions: sessionmaker[Session],
    app_version: str,
    max_bytes: int,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="smoke-shack-restore-") as temporary_name:
        temporary = Path(temporary_name)
        archive_path = temporary / "upload.zip"
        await _save_upload(upload, archive_path, max_bytes)
        manifest = _validate_and_extract(archive_path, temporary)
        uploaded_database = temporary / "smoke-shack.db"
        revision_before = _validate_schema(manifest)
        _check_integrity(uploaded_database)

        with sessions() as session:
            active = session.scalar(
                select(Cook.id).where(Cook.ended_at.is_(None), Cook.status != "planned").limit(1)
            )
        if active is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Finish or end the active cook before restoring",
            )

        safety_name = f"pre-restore-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.zip"
        safety_path = database_path.parent / safety_name
        safety_temp = build_backup(database_path, photo_dir, app_version)
        os.replace(safety_temp, safety_path)

        engine = sessions.kw.get("bind")
        if not isinstance(engine, Engine):
            raise RuntimeError("Restore requires a SQLAlchemy engine-backed session factory")
        _replace_database(uploaded_database, database_path)
        engine.dispose()
        _upgrade_database(database_path)
        _replace_photos(temporary / "photos", photo_dir)
        _rewrite_photo_paths(database_path, photo_dir)
        engine.dispose()

        tables, revision_after = _database_manifest(database_path)
        photo_count = sum(path.is_file() for path in photo_dir.rglob("*"))
        return {
            "tables": tables,
            "photo_count": photo_count,
            "schema_revision_before": revision_before,
            "schema_revision_after": revision_after,
            "safety_copy": safety_name,
        }


async def _save_upload(upload: UploadFile, destination: Path, limit: int) -> None:
    total = 0
    try:
        with destination.open("wb") as target:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > limit:
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        f"Restore upload exceeds {limit} byte limit",
                    )
                target.write(chunk)
    finally:
        await upload.close()


def _validate_and_extract(archive_path: Path, destination: Path) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = set()
            for member in archive.infolist():
                path = PurePosixPath(member.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in member.filename:
                    raise ValueError(f"Unsafe zip member: {member.filename}")
                name = path.as_posix().rstrip("/")
                allowed = name in ALLOWED_FILES or name == "photos" or name.startswith("photos/")
                if not allowed:
                    raise ValueError(f"Unexpected zip member: {member.filename}")
                if name:
                    if name in names:
                        raise ValueError(f"Duplicate zip member: {member.filename}")
                    names.add(name)
            if not ALLOWED_FILES.issubset(names):
                raise ValueError("Backup must contain manifest.json and smoke-shack.db")
            try:
                manifest = json.loads(archive.read("manifest.json"))
            except (json.JSONDecodeError, KeyError) as exc:
                raise ValueError("Invalid manifest.json") from exc
            if not isinstance(manifest, dict) or manifest.get("format_version") != 1:
                raise ValueError("Unsupported backup format_version; expected 1")
            archive.extract("smoke-shack.db", destination)
            database = destination / "smoke-shack.db"
            if manifest.get("db_sha256") != _sha256(database):
                raise ValueError("Database checksum does not match manifest")
            for member in archive.infolist():
                if PurePosixPath(member.filename).as_posix().startswith("photos/"):
                    archive.extract(member, destination)
            return manifest
    except (zipfile.BadZipFile, OSError, ValueError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


def _validate_schema(manifest: dict[str, Any]) -> str:
    revision = manifest.get("schema_revision")
    config = Config("alembic.ini")
    scripts = ScriptDirectory.from_config(config)
    head = scripts.get_current_head()
    if head is None:
        raise RuntimeError("Alembic has no head revision")
    known = {item.revision for item in scripts.walk_revisions("base", head)}
    if not isinstance(revision, str) or revision not in known:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Backup schema revision {revision!r} is newer than this app or unknown",
        )
    return revision


def _check_integrity(database: Path) -> None:
    try:
        with sqlite3.connect(database) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchall()
    except sqlite3.DatabaseError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Corrupt backup database"
        ) from exc
    if result != [("ok",)]:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Backup database integrity check failed: {result[0][0] if result else 'no result'}",
        )


def _replace_database(source_path: Path, destination_path: Path) -> None:
    with sqlite3.connect(source_path) as source, sqlite3.connect(destination_path) as destination:
        source.backup(destination)


def _upgrade_database(database_path: Path) -> None:
    config = Config("alembic.ini")
    config.attributes["database_path"] = str(database_path)
    command.upgrade(config, "head")


def _replace_photos(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for child in destination.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)


def _rewrite_photo_paths(database: Path, photo_dir: Path) -> None:
    with sqlite3.connect(database) as connection:
        photos = connection.execute("SELECT id, cook_id, path FROM photos").fetchall()
        for photo_id, cook_id, old_path in photos:
            new_path = photo_dir / str(cook_id) / Path(old_path).name
            connection.execute("UPDATE photos SET path = ? WHERE id = ?", (str(new_path), photo_id))
        connection.execute(
            "UPDATE events SET photo_path = (SELECT path FROM photos "
            "WHERE photos.event_id = events.id LIMIT 1) WHERE photo_path IS NOT NULL"
        )
        for table, directory in (("meat", "meat"), ("pellets", "pellets"), ("spices", "spices")):
            rows = connection.execute(
                f"SELECT id, photo_path FROM {table} WHERE photo_path IS NOT NULL"
            ).fetchall()
            for item_id, old_path in rows:
                new_path = photo_dir / directory / Path(old_path).name
                connection.execute(
                    f"UPDATE {table} SET photo_path = ? WHERE id = ?",
                    (str(new_path), item_id),
                )
        connection.commit()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
