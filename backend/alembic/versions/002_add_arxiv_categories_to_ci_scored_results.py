"""Add arxiv_categories to ci_scored_results

Revision ID: 002
Revises: 001
Create Date: 2026-03-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ci_scored_results",
        sa.Column("arxiv_categories", ARRAY(sa.String()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ci_scored_results", "arxiv_categories")
