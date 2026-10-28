"""add probe targets to samples

Revision ID: 3f47ec19353c
Revises: ef36b629902e
"""

import sqlalchemy as sa
from alembic import op

revision = "3f47ec19353c"
down_revision = "ef36b629902e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("samples", sa.Column("probe1_target", sa.Float(), nullable=True))
    op.add_column("samples", sa.Column("probe2_target", sa.Float(), nullable=True))


def downgrade():
    op.drop_column("samples", "probe2_target")
    op.drop_column("samples", "probe1_target")
