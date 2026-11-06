"""allow fuel price to be null

Revision ID: c4f91a2d7e30
Revises: b1e7c4a92d6f
"""

import sqlalchemy as sa
from alembic import op

revision = "c4f91a2d7e30"
down_revision = "b1e7c4a92d6f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("fuel") as batch_op:
        batch_op.alter_column(
            "price_per_pound",
            existing_type=sa.Numeric(precision=8, scale=2),
            nullable=True,
        )


def downgrade() -> None:
    op.execute("UPDATE fuel SET price_per_pound = 0 WHERE price_per_pound IS NULL")
    with op.batch_alter_table("fuel") as batch_op:
        batch_op.alter_column(
            "price_per_pound",
            existing_type=sa.Numeric(precision=8, scale=2),
            nullable=False,
        )
