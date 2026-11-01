"""add pellet upc and bag size

Revision ID: c6e8395a2714
Revises: 7da6cbe17b2a
"""

import sqlalchemy as sa
from alembic import op

revision = "c6e8395a2714"
down_revision = "7da6cbe17b2a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pellets", sa.Column("upc", sa.String(length=14), nullable=True))
    op.add_column("pellets", sa.Column("bag_size_lb", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("pellets", "bag_size_lb")
    op.drop_column("pellets", "upc")
