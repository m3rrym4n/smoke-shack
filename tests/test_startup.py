from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.startup import UnknownDatabaseRevision, upgrade_database


def _migrate(database: Path, revision: str) -> None:
    config = Config("alembic.ini")
    config.attributes["database_path"] = str(database)
    command.upgrade(config, revision)


def _revision(database: Path) -> str:
    with sqlite3.connect(database) as connection:
        return connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]


def _copies(database: Path) -> list[Path]:
    return sorted(database.parent.glob("pre-upgrade-*-to-*-*.db"))


def test_fresh_database_reaches_head_without_safety_copy(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"

    assert upgrade_database(database) is None

    assert (
        _revision(database) == ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    )
    assert _copies(database) == []


def test_outdated_database_is_copied_and_upgraded_with_data_intact(tmp_path: Path) -> None:
    database = tmp_path / "outdated.db"
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    head = scripts.get_current_head()
    assert head is not None
    previous = scripts.get_revision(head).down_revision
    assert isinstance(previous, str)
    _migrate(database, previous)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO notes (body,title,scope,created_at) VALUES ('keep','note','gear',?)",
            ("2026-11-05T12:00:00Z",),
        )
        connection.commit()

    safety_copy = upgrade_database(database, now=datetime(2026, 11, 5, 12, 30, tzinfo=UTC))

    assert safety_copy is not None and safety_copy.is_file()
    assert previous in safety_copy.name and head in safety_copy.name
    assert _revision(safety_copy) == previous
    assert _revision(database) == head
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT body FROM notes").fetchone() == ("keep",)


def test_database_at_head_starts_without_safety_copy(tmp_path: Path) -> None:
    database = tmp_path / "current.db"
    _migrate(database, "head")

    assert upgrade_database(database) is None
    assert _copies(database) == []


def test_unknown_revision_is_refused_and_left_untouched(tmp_path: Path) -> None:
    database = tmp_path / "future.db"
    _migrate(database, "head")
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE alembic_version SET version_num = 'future_revision'")
        connection.commit()
    before = database.read_bytes()

    with pytest.raises(UnknownDatabaseRevision, match="refusing to start"):
        upgrade_database(database)

    assert database.read_bytes() == before
    assert _copies(database) == []


def test_only_three_most_recent_safety_copies_are_kept(tmp_path: Path) -> None:
    database = tmp_path / "rotate.db"
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    head = scripts.get_current_head()
    assert head is not None
    previous = scripts.get_revision(head).down_revision
    assert isinstance(previous, str)
    start = datetime(2026, 11, 5, tzinfo=UTC)

    created: list[Path] = []
    for offset in range(4):
        if database.exists():
            config = Config("alembic.ini")
            config.attributes["database_path"] = str(database)
            command.downgrade(config, previous)
        else:
            _migrate(database, previous)
        copy = upgrade_database(database, now=start + timedelta(seconds=offset))
        assert copy is not None
        created.append(copy)

    assert _copies(database) == sorted(created[1:])
    assert not created[0].exists()
