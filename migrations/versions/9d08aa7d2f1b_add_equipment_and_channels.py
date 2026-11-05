"""add equipment and channels

Revision ID: 9d08aa7d2f1b
Revises: 21a15e99d09c
"""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from alembic import op

from app.config import Settings

revision = "9d08aa7d2f1b"
down_revision = "21a15e99d09c"
branch_labels = None
depends_on = None


def _settings() -> Settings:
    settings = Settings.from_env()
    configured_path = Path(settings.entities_path)
    if settings.entities_path == "config/entities.yaml" and not configured_path.exists():
        settings = replace(
            settings,
            entities_path=str(Path(__file__).parents[2] / "config" / "entities.yaml"),
        )
    return settings


def _extra_probe_name(entity_id: str) -> tuple[str, str]:
    key = entity_id.rsplit(".", 1)[-1]
    return key, key.replace("_", " ").title()


def upgrade() -> None:
    op.create_table(
        "equipment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nickname", sa.Text(), nullable=False),
        sa.Column("maker", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("fuel_type", sa.Text(), nullable=True),
        sa.Column("units", sa.String(length=1), server_default="F", nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.CheckConstraint("units IN ('F', 'C')", name="ck_equipment_units"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "channels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("equipment_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=4), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("source_entity", sa.Text(), nullable=False),
        sa.Column("target_entity", sa.Text(), nullable=True),
        sa.Column("calibration_offset", sa.Float(), server_default="0", nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("role IN ('pit', 'meat')", name="ck_channels_role"),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("equipment_id", "key", name="uq_channels_equipment_key"),
    )
    with op.batch_alter_table("cooks") as batch_op:
        batch_op.add_column(sa.Column("equipment_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_cooks_equipment_id_equipment", "equipment", ["equipment_id"], ["id"]
        )

    connection = op.get_bind()
    existing_id = connection.execute(
        sa.text("SELECT id FROM equipment ORDER BY id LIMIT 1")
    ).scalar_one_or_none()
    if existing_id is None:
        settings = _settings()
        entities = settings.load_entities()
        timestamp = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        equipment_id = connection.execute(
            sa.text(
                "INSERT INTO equipment "
                "(nickname, maker, model, type, fuel_type, units, created_at, updated_at) "
                "VALUES (:nickname, NULL, NULL, 'pellet', 'pellets', 'F', :now, :now) "
                "RETURNING id"
            ),
            {"nickname": settings.grill_name or "Grill", "now": timestamp},
        ).scalar_one()
        channels = [
            ("pit", "pit", "Pit", entities.pit_temp, None),
            ("probe1", "meat", "Probe 1", entities.probe1_temp, entities.probe1_climate),
            ("probe2", "meat", "Probe 2", entities.probe2_temp, entities.probe2_climate),
        ]
        for entity_id in entities.extra_probes:
            key, label = _extra_probe_name(entity_id)
            channels.append((key, "meat", label, entity_id, None))
        connection.execute(
            sa.text(
                "INSERT INTO channels "
                "(equipment_id, key, role, label, source_entity, target_entity, "
                "calibration_offset, position) VALUES "
                "(:equipment_id, :key, :role, :label, :source_entity, :target_entity, 0, :position)"
            ),
            [
                {
                    "equipment_id": equipment_id,
                    "key": key,
                    "role": role,
                    "label": label,
                    "source_entity": source,
                    "target_entity": target,
                    "position": position,
                }
                for position, (key, role, label, source, target) in enumerate(channels)
            ],
        )
        existing_id = equipment_id

    connection.execute(
        sa.text("UPDATE cooks SET equipment_id = :equipment_id WHERE equipment_id IS NULL"),
        {"equipment_id": existing_id},
    )


def downgrade() -> None:
    with op.batch_alter_table("cooks") as batch_op:
        batch_op.drop_constraint("fk_cooks_equipment_id_equipment", type_="foreignkey")
        batch_op.drop_column("equipment_id")
    op.drop_table("channels")
    op.drop_table("equipment")
