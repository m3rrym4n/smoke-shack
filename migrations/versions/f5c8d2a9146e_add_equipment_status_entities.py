"""add equipment status entities

Revision ID: f5c8d2a9146e
Revises: 7c3e1a4b9f20
"""

import sqlalchemy as sa
from alembic import op

revision = "f5c8d2a9146e"
down_revision = "7c3e1a4b9f20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("equipment") as batch_op:
        batch_op.add_column(sa.Column("stale_after_seconds", sa.Integer(), nullable=True))
    op.create_table(
        "equipment_entities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("equipment_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("equipment_id", "role", name="uq_equipment_entities_equipment_role"),
    )


def downgrade() -> None:
    op.drop_table("equipment_entities")
    with op.batch_alter_table("equipment") as batch_op:
        batch_op.drop_column("stale_after_seconds")
