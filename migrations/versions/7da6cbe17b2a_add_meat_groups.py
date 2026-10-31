"""add meat groups

Revision ID: 7da6cbe17b2a
Revises: 4b825e65bd0a
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "7da6cbe17b2a"
down_revision = "4b825e65bd0a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEEDS = {
    "Pork shoulder": ("pork butt", "pork shoulder picnic"),
    "Pork ribs": ("pork spare ribs", "pork baby back ribs"),
    "Beef ribs": ("beef short rib", "beef back rib"),
    "Leg roasts": ("boneless leg of lamb", "bone in leg of goat", "bone in beef leg"),
}


def upgrade() -> None:
    op.create_table(
        "meat_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        "uq_meat_groups_name_ci", "meat_groups", [sa.text("lower(name)")], unique=True
    )
    op.create_table(
        "meat_group_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("meat_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type_key", sa.String(), nullable=False, unique=True),
    )

    connection = op.get_bind()
    existing = {
        row[0]
        for row in connection.execute(sa.text("SELECT DISTINCT lower(trim(type)) FROM meat"))
    }
    for name, type_keys in SEEDS.items():
        result = connection.execute(
            sa.text("INSERT OR IGNORE INTO meat_groups (name) VALUES (:name)"), {"name": name}
        )
        group_id = result.lastrowid
        if not group_id:
            group_id = connection.execute(
                sa.text("SELECT id FROM meat_groups WHERE lower(name) = lower(:name)"),
                {"name": name},
            ).scalar_one()
        for type_key in type_keys:
            if type_key in existing:
                connection.execute(
                    sa.text(
                        "INSERT OR IGNORE INTO meat_group_types (group_id, type_key) "
                        "VALUES (:group_id, :type_key)"
                    ),
                    {"group_id": group_id, "type_key": type_key},
                )


def downgrade() -> None:
    op.drop_table("meat_group_types")
    op.drop_index("uq_meat_groups_name_ci", table_name="meat_groups")
    op.drop_table("meat_groups")
