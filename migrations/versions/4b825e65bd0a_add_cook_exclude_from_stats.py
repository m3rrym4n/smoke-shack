"""add cook exclude from stats

Revision ID: 4b825e65bd0a
Revises: d7f392bc6a10
"""

import sqlalchemy as sa
from alembic import op

revision = "4b825e65bd0a"
down_revision = "d7f392bc6a10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cooks",
        sa.Column(
            "exclude_from_stats",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("cooks", "exclude_from_stats")
