"""add pellet emptied date

Revision ID: 21a15e99d09c
Revises: c6e8395a2714
"""

import sqlalchemy as sa
from alembic import op

revision = "21a15e99d09c"
down_revision = "c6e8395a2714"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pellets", sa.Column("emptied_on", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("pellets", "emptied_on")
