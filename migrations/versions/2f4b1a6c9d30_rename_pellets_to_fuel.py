"""rename pellets to fuel

Revision ID: 2f4b1a6c9d30
Revises: f5c8d2a9146e
"""

import sqlalchemy as sa
from alembic import op

revision = "2f4b1a6c9d30"
down_revision = "f5c8d2a9146e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("pellets", "fuel")
    op.add_column(
        "fuel",
        sa.Column("type", sa.String(length=10), nullable=False, server_default="pellets"),
    )
    with op.batch_alter_table("fuel") as batch_op:
        batch_op.create_check_constraint(
            "ck_fuel_type", "type IN ('pellets', 'charcoal', 'wood')"
        )
        batch_op.alter_column("type", server_default=None)
    with op.batch_alter_table("cooks") as batch_op:
        batch_op.alter_column("pellet_id", new_column_name="fuel_id")


def downgrade() -> None:
    with op.batch_alter_table("cooks") as batch_op:
        batch_op.alter_column("fuel_id", new_column_name="pellet_id")
    with op.batch_alter_table("fuel") as batch_op:
        batch_op.drop_constraint("ck_fuel_type", type_="check")
        batch_op.drop_column("type")
    op.rename_table("fuel", "pellets")
