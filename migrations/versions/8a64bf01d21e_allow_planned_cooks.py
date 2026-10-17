"""allow planned cooks without a start time

Revision ID: 8a64bf01d21e
Revises: 3f47ec19353c
"""

import sqlalchemy as sa
from alembic import op

revision = "8a64bf01d21e"
down_revision = "3f47ec19353c"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("cooks") as batch_op:
        batch_op.alter_column(
            "started_at", existing_type=sa.String(length=32), nullable=True
        )


def downgrade():
    with op.batch_alter_table("cooks") as batch_op:
        batch_op.alter_column(
            "started_at", existing_type=sa.String(length=32), nullable=False
        )
