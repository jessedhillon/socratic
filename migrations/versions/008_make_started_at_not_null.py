"""Make started_at NOT NULL with DEFAULT NOW().

Revision ID: 008
Revises: 007
Create Date: 2026-01-23

The started_at column was never being populated, causing queries that
ORDER BY started_at to return undefined results. This migration:
1. Backfills NULL values using completed_at (or NOW() if also NULL)
2. Sets server_default to NOW() for future inserts
3. Makes the column NOT NULL

Timezone notes:
- Column is timestamptz, which stores internally as UTC
- NOW() returns current moment in session timezone, converted to UTC for storage
- Safe regardless of client timezone settings
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "008_started_at_not_null"
down_revision = "007_word_timings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Backfill NULL started_at values
    # Use completed_at if available, otherwise use current time
    op.execute(
        """
        UPDATE assessment_attempts
        SET started_at = COALESCE(completed_at, NOW())
        WHERE started_at IS NULL
        """
    )

    # Step 2: Set server default for future inserts
    op.alter_column(
        "assessment_attempts",
        "started_at",
        server_default=sa.func.now(),
    )

    # Step 3: Make column NOT NULL
    op.alter_column(
        "assessment_attempts",
        "started_at",
        nullable=False,
    )


def downgrade() -> None:
    # Remove NOT NULL constraint
    op.alter_column(
        "assessment_attempts",
        "started_at",
        nullable=True,
    )

    # Remove server default
    op.alter_column(
        "assessment_attempts",
        "started_at",
        server_default=None,
    )
