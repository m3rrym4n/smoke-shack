from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path


def build_backup(
    database_path: str | Path,
    photo_dir: str | Path,
    showcase_dir: str | Path,
    app_version: str,
    *,
    created_at: datetime | None = None,
) -> Path:
    """Build a complete backup archive in a temporary file.

    The caller owns the returned path and must delete it after use.
    """
    database_directory = Path(database_path).parent
    archive_file = tempfile.NamedTemporaryFile(
        prefix="smoke-shack-backup-",
        suffix=".zip",
        dir=database_directory,
        delete=False,
    )
    archive_path = Path(archive_file.name)
    archive_file.close()

    snapshot_file = tempfile.NamedTemporaryFile(
        prefix="smoke-shack-db-",
        suffix=".db",
        dir=database_directory,
        delete=False,
    )
    snapshot_path = Path(snapshot_file.name)
    snapshot_file.close()

    try:
        snapshot_database(Path(database_path), snapshot_path)
        tables, schema_revision = _database_manifest(snapshot_path)
        photos = sorted(path for path in Path(photo_dir).rglob("*") if path.is_file())
        showcase_files = sorted(path for path in Path(showcase_dir).rglob("*") if path.is_file())
        timestamp = (created_at or datetime.now(UTC)).astimezone(UTC)
        manifest = {
            "format_version": 1,
            "app_version": app_version,
            "schema_revision": schema_revision,
            "created_at": timestamp.isoformat().replace("+00:00", "Z"),
            "tables": tables,
            "photo_count": len(photos),
            "showcase_count": len(showcase_files),
            "db_sha256": _sha256(snapshot_path),
        }

        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot_path, "smoke-shack.db")
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
            root = Path(photo_dir)
            for photo in photos:
                archive.write(photo, Path("photos") / photo.relative_to(root))
            showcase_root = Path(showcase_dir)
            for showcase_file in showcase_files:
                archive.write(
                    showcase_file,
                    Path("showcase") / showcase_file.relative_to(showcase_root),
                )
    except Exception:
        archive_path.unlink(missing_ok=True)
        raise
    finally:
        snapshot_path.unlink(missing_ok=True)

    return archive_path


def snapshot_database(source_path: Path, destination_path: Path) -> None:
    """Create a consistent SQLite snapshot, including committed WAL contents."""
    with sqlite3.connect(source_path) as source, sqlite3.connect(destination_path) as destination:
        source.backup(destination)


def _database_manifest(snapshot_path: Path) -> tuple[dict[str, int], str | None]:
    with sqlite3.connect(snapshot_path) as connection:
        table_names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        counts = {}
        for name in table_names:
            quoted_name = name.replace('"', '""')
            row = connection.execute(f'SELECT COUNT(*) FROM "{quoted_name}"').fetchone()
            counts[name] = row[0]
        if "alembic_version" not in table_names:
            revision = None
        else:
            row = connection.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()
            revision = row[0] if row else None
    return counts, revision


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
