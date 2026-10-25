"""add cooked to meat

Revision ID: b67a21d9942f
Revises: 8a64bf01d21e
"""

import sqlalchemy as sa
from alembic import op

revision = "b67a21d9942f"
down_revision = "8a64bf01d21e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "meat",
        sa.Column("cooked", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade():
    op.drop_column("meat", "cooked")
