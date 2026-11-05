from __future__ import annotations

import logging
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.backup import snapshot_database
from app.config import Settings

LOGGER = logging.getLogger("smoke_shack.startup")
SAFETY_COPY_LIMIT = 3


class UnknownDatabaseRevision(RuntimeError):
    """Raised when the database was created by an unknown app schema."""


def _alembic_config(database_path: Path) -> Config:
    config = Config("alembic.ini")
    config.attributes["database_path"] = str(database_path)
    return config


def _database_state(database_path: Path) -> tuple[bool, str | None]:
    if not database_path.is_file() or database_path.stat().st_size == 0:
        return False, None

    uri = f"file:{quote(database_path.resolve().as_posix())}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        if not tables:
            return False, None
        if "alembic_version" not in tables:
            return True, None
        revisions = [
            row[0] for row in connection.execute("SELECT version_num FROM alembic_version")
        ]
    return True, revisions[0] if len(revisions) == 1 else None


def _prune_safety_copies(database_path: Path) -> None:
    copies = sorted(
        database_path.parent.glob("pre-upgrade-*-to-*-*.db"),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )
    for old_copy in copies[SAFETY_COPY_LIMIT:]:
        old_copy.unlink()


def upgrade_database(database_path: Path, *, now: datetime | None = None) -> Path | None:
    """Back up an existing outdated database and migrate it to Alembic head."""
    config = _alembic_config(database_path)
    scripts = ScriptDirectory.from_config(config)
    head = scripts.get_current_head()
    if head is None:
        raise RuntimeError("Alembic has no head revision")

    has_tables, current = _database_state(database_path)
    known = {revision.revision for revision in scripts.walk_revisions("base", head)}
    if has_tables and current not in known:
        raise UnknownDatabaseRevision(
            f"Database schema revision {current!r} is newer than this app or unknown; "
            "refusing to start without changing the database"
        )

    safety_copy = None
    if has_tables and current != head:
        timestamp = (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%d-%H%M%S-%fZ")
        safety_copy = database_path.with_name(f"pre-upgrade-{current}-to-{head}-{timestamp}.db")
        snapshot_database(database_path, safety_copy)
        _prune_safety_copies(database_path)
        LOGGER.info(
            "Created pre-upgrade safety copy %s before migrating %s to %s",
            safety_copy,
            current,
            head,
        )

    if current != head:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        command.upgrade(config, "head")
        LOGGER.info("Database schema is at Alembic head %s", head)
    return safety_copy


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    database_path = Path(Settings.from_env().database_path)
    try:
        upgrade_database(database_path)
    except UnknownDatabaseRevision as exc:
        LOGGER.critical("%s", exc)
        return 1

    os.execvp(
        "uvicorn",
        ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
