from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_upgrade_from_previous_head_preserves_existing_cooks(
    tmp_path: Path, monkeypatch: object
) -> None:
    database = tmp_path / "migration.db"
    monkeypatch.setenv("DATABASE_PATH", str(database))  # type: ignore[attr-defined]
    config = Config("alembic.ini")
    command.upgrade(config, "3f47ec19353c")
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO cooks "
                "(started_at, status, rotisserie, has_gap, incomplete, created_at, updated_at) "
                "VALUES ('2026-10-16T16:57:03Z', 'closed', 0, 0, 0, "
                "'2026-10-16T16:57:03Z', '2026-10-16T16:57:03Z')"
            )
        )

    command.upgrade(config, "head")

    started = next(
        column
        for column in inspect(engine).get_columns("cooks")
        if column["name"] == "started_at"
    )
    with engine.connect() as connection:
        row = connection.execute(text("SELECT started_at, status FROM cooks")).one()
    assert started["nullable"] is True
    assert row == ("2026-10-16T16:57:03Z", "closed")
