from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.config import Settings


def migration_config() -> Config:
    repository = Path(__file__).parent.parent
    config = Config(repository / "alembic.ini")
    config.set_main_option("script_location", str(repository / "migrations"))
    return config


def test_migration_chain_has_exactly_one_head() -> None:
    script = ScriptDirectory.from_config(Config("alembic.ini"))

    assert len(script.get_heads()) == 1, (
        "multiple Alembic heads: merge or re-parent the newer migration"
    )


def test_supervisor_migrations_use_app_database_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    working_directory = tmp_path / "working"
    data_directory = tmp_path / "data"
    working_directory.mkdir()
    data_directory.mkdir()
    monkeypatch.chdir(working_directory)
    monkeypatch.setenv("SUPERVISOR_TOKEN", "supervisor-secret")
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    app_settings = Settings.from_env()
    redirected_database = data_directory / Path(app_settings.database_path).name
    monkeypatch.setattr(
        Settings,
        "from_env",
        classmethod(lambda cls: Settings(database_path=str(redirected_database))),
    )

    command.upgrade(migration_config(), "head")

    assert app_settings.database_path == "/data/smoke-shack.db"
    assert "spices" in inspect(create_engine(f"sqlite:///{redirected_database}")).get_table_names()
    assert not (working_directory / "smoke-stack.db").exists()


def test_migrations_honor_explicit_database_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "explicit.db"
    monkeypatch.setenv("SUPERVISOR_TOKEN", "supervisor-secret")
    monkeypatch.setenv("DATABASE_PATH", str(database))

    command.upgrade(migration_config(), "head")

    assert "spices" in inspect(create_engine(f"sqlite:///{database}")).get_table_names()


def test_migrations_keep_default_database_path_without_supervisor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    monkeypatch.delenv("DATABASE_PATH", raising=False)

    command.upgrade(migration_config(), "head")

    database = tmp_path / "smoke-stack.db"
    assert "spices" in inspect(create_engine(f"sqlite:///{database}")).get_table_names()


def test_empty_database_upgrades_to_complete_head(
    tmp_path: Path, monkeypatch: object
) -> None:
    database = tmp_path / "empty-to-head.db"
    monkeypatch.setenv("DATABASE_PATH", str(database))  # type: ignore[attr-defined]
    config = Config("alembic.ini")

    command.upgrade(config, "head")

    schema = inspect(create_engine(f"sqlite:///{database}"))
    assert "spices" in schema.get_table_names()
    assert "cook_spices" in schema.get_table_names()
    assert "cooked" in {column["name"] for column in schema.get_columns("meat")}
    assert "photo_path" in {column["name"] for column in schema.get_columns("meat")}
    assert "photo_path" in {column["name"] for column in schema.get_columns("pellets")}
    assert "upc" in {column["name"] for column in schema.get_columns("pellets")}
    assert "bag_size_lb" in {column["name"] for column in schema.get_columns("pellets")}
    assert "emptied_on" in {column["name"] for column in schema.get_columns("pellets")}
    assert "photo_path" in {column["name"] for column in schema.get_columns("spices")}
    assert "meat_groups" in schema.get_table_names()
    assert "meat_group_types" in schema.get_table_names()
    assert "equipment" in schema.get_table_names()
    assert "channels" in schema.get_table_names()
    with create_engine(f"sqlite:///{database}").connect() as connection:
        assert connection.execute(text("SELECT nickname FROM equipment")).scalar_one() == "Grill"
        assert connection.execute(text("SELECT count(*) FROM channels")).scalar_one() == 3


def test_equipment_migration_seeds_channels_and_links_existing_cooks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "equipment.db"
    entities = tmp_path / "entities.yaml"
    entities.write_text(
        """pit_climate: climate.grill
pit_temp: sensor.grill_pit
probe1_temp: sensor.grill_food_one
probe2_temp: sensor.grill_food_two
probe1_connection: binary_sensor.grill_probe_one
probe2_connection: binary_sensor.grill_probe_two
probe1_climate: climate.grill_probe_one
probe2_climate: climate.grill_probe_two
fire_state: sensor.grill_fire
power_state: sensor.grill_power
warning: sensor.grill_warning
extra_probes:
  - sensor.ambient_left
"""
    )
    monkeypatch.setenv("DATABASE_PATH", str(database))
    monkeypatch.setenv("ENTITIES_CONFIG", str(entities))
    monkeypatch.setenv("SMOKE_STACK_GRILL_NAME", "Legacy Grill")
    monkeypatch.setenv("SMOKE_SHACK_GRILL_NAME", "Back Patio")
    config = Config("alembic.ini")
    command.upgrade(config, "21a15e99d09c")
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO cooks "
                "(started_at, status, rotisserie, has_gap, incomplete, exclude_from_stats, "
                "created_at, updated_at) VALUES "
                "('2026-10-16T16:57:03Z', 'closed', 0, 0, 0, 0, "
                "'2026-10-16T16:57:03Z', '2026-10-16T16:57:03Z')"
            )
        )
        cook_id = connection.execute(text("SELECT id FROM cooks")).scalar_one()
        connection.execute(
            text(
                "INSERT INTO samples (cook_id, ts, extra_probes) "
                "VALUES (:cook_id, '2026-10-16T16:58:03Z', '{}')"
            ),
            {"cook_id": cook_id},
        )

    command.upgrade(config, "head")
    with engine.connect() as connection:
        equipment = connection.execute(
            text("SELECT id, nickname, maker, model, type, fuel_type, units FROM equipment")
        ).one()
        channels = connection.execute(
            text(
                "SELECT key, role, label, source_entity, target_entity, calibration_offset, "
                "position FROM channels ORDER BY position"
            )
        ).all()
        cook = connection.execute(
            text("SELECT equipment_id, started_at, status FROM cooks")
        ).one()
        sample = connection.execute(
            text("SELECT cook_id, ts, extra_probes FROM samples")
        ).one()

    assert equipment[1:] == ("Back Patio", None, None, "pellet", "pellets", "F")
    assert channels == [
        ("pit", "pit", "Pit", "sensor.grill_pit", None, 0.0, 0),
        ("probe1", "meat", "Probe 1", "sensor.grill_food_one", "climate.grill_probe_one", 0.0, 1),
        ("probe2", "meat", "Probe 2", "sensor.grill_food_two", "climate.grill_probe_two", 0.0, 2),
        ("ambient_left", "meat", "Ambient Left", "sensor.ambient_left", None, 0.0, 3),
    ]
    assert cook == (equipment.id, "2026-10-16T16:57:03Z", "closed")
    assert sample == (cook_id, "2026-10-16T16:58:03Z", "{}")

    command.downgrade(config, "21a15e99d09c")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM equipment")).scalar_one() == 1
        assert connection.execute(text("SELECT count(*) FROM channels")).scalar_one() == 4


def test_meat_groups_migration_seeds_all_types_idempotently(
    tmp_path: Path, monkeypatch: object
) -> None:
    database = tmp_path / "meat-groups.db"
    monkeypatch.setenv("DATABASE_PATH", str(database))  # type: ignore[attr-defined]
    config = Config("alembic.ini")
    command.upgrade(config, "4b825e65bd0a")
    engine = create_engine(f"sqlite:///{database}")

    command.upgrade(config, "head")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        groups = connection.execute(text("SELECT name FROM meat_groups ORDER BY name")).scalars()
        types = connection.execute(text("SELECT type_key FROM meat_group_types")).scalars()
        group_count = connection.execute(text("SELECT count(*) FROM meat_groups")).scalar_one()
        type_count = connection.execute(
            text("SELECT count(*) FROM meat_group_types")
        ).scalar_one()

    assert list(groups) == ["Beef ribs", "Leg roasts", "Pork ribs", "Pork shoulder"]
    assert set(types) == {
        "pork butt",
        "pork shoulder picnic",
        "pork spare ribs",
        "pork baby back ribs",
        "beef short rib",
        "beef back rib",
        "boneless leg of lamb",
        "bone in leg of goat",
        "bone in beef leg",
    }
    assert group_count == 4
    assert type_count == 9


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


def test_cooked_migration_defaults_existing_meat_to_false(
    tmp_path: Path, monkeypatch: object
) -> None:
    database = tmp_path / "meat-migration.db"
    monkeypatch.setenv("DATABASE_PATH", str(database))  # type: ignore[attr-defined]
    config = Config("alembic.ini")
    command.upgrade(config, "8a64bf01d21e")
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO meat (type, pounds, price_per_pound, purchased_on) "
                "VALUES ('Pork butt', 8.5, 2.49, '2026-10-16')"
            )
        )

    command.upgrade(config, "head")

    cooked_column = next(
        column for column in inspect(engine).get_columns("meat") if column["name"] == "cooked"
    )
    with engine.connect() as connection:
        cooked = connection.execute(text("SELECT cooked FROM meat")).scalar_one()
    assert cooked_column["nullable"] is False
    assert cooked == 0


def test_exclude_from_stats_migration_defaults_existing_cooks_to_false(
    tmp_path: Path, monkeypatch: object
) -> None:
    database = tmp_path / "exclude-stats-migration.db"
    monkeypatch.setenv("DATABASE_PATH", str(database))  # type: ignore[attr-defined]
    config = Config("alembic.ini")
    command.upgrade(config, "d7f392bc6a10")
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

    column = next(
        item
        for item in inspect(engine).get_columns("cooks")
        if item["name"] == "exclude_from_stats"
    )
    with engine.connect() as connection:
        value = connection.execute(text("SELECT exclude_from_stats FROM cooks")).scalar_one()
    assert column["nullable"] is False
    assert value == 0


def test_pellet_fields_migration_preserves_existing_rows(
    tmp_path: Path, monkeypatch: object
) -> None:
    database = tmp_path / "pellet-fields.db"
    monkeypatch.setenv("DATABASE_PATH", str(database))  # type: ignore[attr-defined]
    config = Config("alembic.ini")
    command.upgrade(config, "7da6cbe17b2a")
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO pellets (vendor, product_name, price_per_pound, purchased_on) "
                "VALUES ('Bear Mountain', 'Oak', 1.25, '2026-10-16')"
            )
        )

    command.upgrade(config, "head")

    columns = {column["name"]: column for column in inspect(engine).get_columns("pellets")}
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT vendor, product_name, upc, bag_size_lb FROM pellets")
        ).one()
    assert columns["upc"]["nullable"] is True
    assert columns["bag_size_lb"]["nullable"] is True
    assert row == ("Bear Mountain", "Oak", None, None)


def test_pellet_emptied_on_migration_preserves_existing_rows(
    tmp_path: Path, monkeypatch: object
) -> None:
    database = tmp_path / "pellet-emptied-on.db"
    monkeypatch.setenv("DATABASE_PATH", str(database))  # type: ignore[attr-defined]
    config = Config("alembic.ini")
    command.upgrade(config, "c6e8395a2714")
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO pellets (vendor, product_name, price_per_pound, purchased_on) "
                "VALUES ('Bear Mountain', 'Oak', 1.25, '2026-10-16')"
            )
        )

    command.upgrade(config, "head")

    columns = {column["name"]: column for column in inspect(engine).get_columns("pellets")}
    with engine.connect() as connection:
        emptied_on = connection.execute(text("SELECT emptied_on FROM pellets")).scalar_one()
    assert columns["emptied_on"]["nullable"] is True
    assert emptied_on is None
