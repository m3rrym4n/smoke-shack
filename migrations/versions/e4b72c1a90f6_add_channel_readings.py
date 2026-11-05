"""add channel readings

Revision ID: e4b72c1a90f6
Revises: 9d08aa7d2f1b
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import sqlalchemy as sa
from alembic import op

revision = "e4b72c1a90f6"
down_revision = "9d08aa7d2f1b"
branch_labels = None
depends_on = None

BATCH_SIZE = 1_000


def _channel_key(raw_key: str) -> str:
    return raw_key.rsplit(".", 1)[-1]


def _channel_label(key: str) -> str:
    return key.replace("_", " ").title()


def _extra_values(raw: Any) -> Mapping[str, Any]:
    if raw is None:
        return {}
    value = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(value, dict):
        raise RuntimeError("Cannot convert samples.extra_probes: expected a JSON object")
    return value


def _convert_fixed_readings(connection: sa.Connection) -> None:
    for key, value, target in (
        ("pit", "pit_temp", "setpoint"),
        ("probe1", "probe1", "probe1_target"),
        ("probe2", "probe2", "probe2_target"),
    ):
        connection.execute(
            sa.text(
                f"INSERT INTO channel_readings (sample_id, channel_id, value, target) "
                f"SELECT samples.id, channels.id, samples.{value}, samples.{target} "
                "FROM samples "
                "JOIN cooks ON cooks.id = samples.cook_id "
                "JOIN channels ON channels.equipment_id = cooks.equipment_id "
                "AND channels.key = :key "
                f"WHERE samples.{value} IS NOT NULL OR samples.{target} IS NOT NULL"
            ),
            {"key": key},
        )


def _convert_extra_readings(connection: sa.Connection) -> None:
    channels = {
        (row.equipment_id, row.key): row.id
        for row in connection.execute(
            sa.text("SELECT id, equipment_id, key FROM channels")
        )
    }
    positions = {
        row.equipment_id: row.next_position
        for row in connection.execute(
            sa.text(
                "SELECT equipment_id, COALESCE(MAX(position), -1) + 1 AS next_position "
                "FROM channels GROUP BY equipment_id"
            )
        )
    }
    last_id = 0
    while True:
        samples = connection.execute(
            sa.text(
                "SELECT samples.id, cooks.equipment_id, samples.extra_probes "
                "FROM samples JOIN cooks ON cooks.id = samples.cook_id "
                "WHERE samples.id > :last_id ORDER BY samples.id LIMIT :batch_size"
            ),
            {"last_id": last_id, "batch_size": BATCH_SIZE},
        ).all()
        if not samples:
            break
        readings: list[dict[str, Any]] = []
        for sample in samples:
            for raw_key, value in _extra_values(sample.extra_probes).items():
                if value is None:
                    continue
                key = _channel_key(str(raw_key))
                channel_id = channels.get((sample.equipment_id, key))
                if channel_id is None:
                    position = positions.get(sample.equipment_id, 0)
                    channel_id = connection.execute(
                        sa.text(
                            "INSERT INTO channels "
                            "(equipment_id, key, role, label, source_entity, target_entity, "
                            "calibration_offset, position) "
                            "VALUES (:equipment_id, :key, 'meat', :label, :source_entity, "
                            "NULL, 0, :position) RETURNING id"
                        ),
                        {
                            "equipment_id": sample.equipment_id,
                            "key": key,
                            "label": _channel_label(key),
                            "source_entity": str(raw_key),
                            "position": position,
                        },
                    ).scalar_one()
                    channels[(sample.equipment_id, key)] = channel_id
                    positions[sample.equipment_id] = position + 1
                readings.append(
                    {"sample_id": sample.id, "channel_id": channel_id, "value": value}
                )
        if readings:
            connection.execute(
                sa.text(
                    "INSERT INTO channel_readings "
                    "(sample_id, channel_id, value, target) "
                    "VALUES (:sample_id, :channel_id, :value, NULL)"
                ),
                readings,
            )
        last_id = samples[-1].id
        if op.get_context().config.attributes.get("fail_channel_readings_after_batch"):
            raise RuntimeError("Forced channel readings conversion failure")


def _verify_conversion(connection: sa.Connection) -> None:
    mismatch = connection.execute(
        sa.text(
            "WITH expected AS ("
            " SELECT cooks.id AS cook_id,"
            " COALESCE(SUM((samples.pit_temp IS NOT NULL OR samples.setpoint IS NOT NULL)"
            " + (samples.probe1 IS NOT NULL OR samples.probe1_target IS NOT NULL)"
            " + (samples.probe2 IS NOT NULL OR samples.probe2_target IS NOT NULL)), 0)"
            " + COALESCE(SUM((SELECT COUNT(*) FROM json_each(samples.extra_probes)"
            " WHERE json_each.value IS NOT NULL)), 0) AS count"
            " FROM cooks LEFT JOIN samples ON samples.cook_id = cooks.id GROUP BY cooks.id"
            "), converted AS ("
            " SELECT samples.cook_id, COUNT(*) AS count FROM channel_readings"
            " JOIN samples ON samples.id = channel_readings.sample_id"
            " GROUP BY samples.cook_id"
            ") SELECT expected.cook_id, expected.count, COALESCE(converted.count, 0)"
            " FROM expected LEFT JOIN converted ON converted.cook_id = expected.cook_id"
            " WHERE expected.count != COALESCE(converted.count, 0) LIMIT 1"
        )
    ).first()
    if mismatch is not None:
        raise RuntimeError(
            "Channel readings conversion failed validation for cook "
            f"{mismatch[0]}: expected {mismatch[1]}, converted {mismatch[2]}"
        )


def upgrade() -> None:
    op.create_table(
        "channel_readings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sample_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("target", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"]),
        sa.ForeignKeyConstraint(["sample_id"], ["samples.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "sample_id", "channel_id", name="uq_channel_readings_sample_channel"
        ),
    )
    op.create_index(
        "ix_channel_readings_channel_sample",
        "channel_readings",
        ["channel_id", "sample_id"],
    )
    connection = op.get_bind()
    _convert_fixed_readings(connection)
    _convert_extra_readings(connection)
    _verify_conversion(connection)


def downgrade() -> None:
    op.drop_index("ix_channel_readings_channel_sample", table_name="channel_readings")
    op.drop_table("channel_readings")
