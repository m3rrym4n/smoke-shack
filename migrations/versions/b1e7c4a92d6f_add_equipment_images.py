"""add equipment images

Revision ID: b1e7c4a92d6f
Revises: 2f4b1a6c9d30
"""

import shutil
from pathlib import Path

import sqlalchemy as sa
from alembic import op

from app.config import Settings

revision = "b1e7c4a92d6f"
down_revision = "2f4b1a6c9d30"
branch_labels = None
depends_on = None

IMAGE_SUFFIXES = (".png", ".jpg", ".webp", ".svg")


def _legacy_image(showcase_dir: Path, kind: str) -> Path | None:
    return next(
        (
            showcase_dir / f"{kind}{suffix}"
            for suffix in IMAGE_SUFFIXES
            if (showcase_dir / f"{kind}{suffix}").is_file()
        ),
        None,
    )


def upgrade() -> None:
    with op.batch_alter_table("equipment") as batch_op:
        batch_op.add_column(sa.Column("photo_path", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("logo_path", sa.Text(), nullable=True))

    settings = Settings.from_env()
    try:
        pit_entity = settings.load_entities().pit_temp
    except (OSError, ValueError):
        return
    connection = op.get_bind()
    equipment_id = connection.execute(
        sa.text(
            "SELECT equipment.id FROM equipment JOIN channels "
            "ON channels.equipment_id = equipment.id "
            "WHERE channels.role = 'pit' AND channels.source_entity = :entity "
            "ORDER BY equipment.id LIMIT 1"
        ),
        {"entity": pit_entity},
    ).scalar_one_or_none()
    if equipment_id is None:
        return

    photo_dir = Path(settings.photo_dir)
    showcase_dir = photo_dir.parent / "showcase"
    destination = photo_dir / "equipment" / str(equipment_id)
    updates: dict[str, str] = {}
    for kind in ("photo", "logo"):
        source = _legacy_image(showcase_dir, kind)
        if source is None:
            continue
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / f"{kind}{source.suffix}"
        shutil.copy2(source, target)
        updates[f"{kind}_path"] = str(target)
    if updates:
        assignments = ", ".join(f"{column} = :{column}" for column in updates)
        connection.execute(
            sa.text(f"UPDATE equipment SET {assignments} WHERE id = :equipment_id"),
            {**updates, "equipment_id": equipment_id},
        )


def downgrade() -> None:
    with op.batch_alter_table("equipment") as batch_op:
        batch_op.drop_column("logo_path")
        batch_op.drop_column("photo_path")
