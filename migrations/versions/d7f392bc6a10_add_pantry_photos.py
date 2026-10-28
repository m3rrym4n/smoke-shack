"""add pantry photos

Revision ID: d7f392bc6a10
Revises: a53a6f4c12de
"""

import sqlalchemy as sa
from alembic import op

revision = "d7f392bc6a10"
down_revision = "a53a6f4c12de"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("pellets", sa.Column("photo_path", sa.String(), nullable=True))
    op.add_column("meat", sa.Column("photo_path", sa.String(), nullable=True))
    op.add_column("spices", sa.Column("photo_path", sa.String(), nullable=True))


def downgrade():
    op.drop_column("spices", "photo_path")
    op.drop_column("meat", "photo_path")
    op.drop_column("pellets", "photo_path")
