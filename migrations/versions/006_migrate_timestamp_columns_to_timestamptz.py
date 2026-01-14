"""migrate timestamp columns to timestamptz

Revision ID: 006_timestamptz
Revises: 005_drop_weight
Create Date: 2026-01-14 12:29:26.719148

Migrates all timestamp columns from `timestamp without time zone` to
`timestamp with time zone`. Existing data is interpreted as UTC.

This enables proper timezone-aware datetime handling throughout the
application, preventing TypeError when comparing timezone-aware and
naive datetimes.
"""

import typing as t

from alembic import op
from sqlalchemy import text

from socratic.lib.sql import ExtendedOperations

# revision identifiers, used by Alembic.
revision: str = "006_timestamptz"
down_revision: str | None = "005_drop_weight"
branch_labels: str | t.Sequence[str] | None = None
depends_on: str | t.Sequence[str] | None = None


# All timestamp columns to migrate, grouped by table
TimestampColumns: dict[str, list[str]] = {
    "agent_states": ["update_time"],
    "assessment_attempts": ["completed_at", "create_time", "started_at"],
    "assignments": ["available_from", "available_until", "create_time", "update_time"],
    "educator_overrides": ["create_time"],
    "evaluation_results": ["create_time"],
    "objectives": ["create_time", "update_time"],
    "organization_memberships": ["create_time", "update_time"],
    "organizations": ["create_time", "update_time"],
    "strands": ["create_time", "update_time"],
    "transcript_segments": ["end_time", "start_time"],
    "users": ["create_time", "update_time"],
}


def upgrade() -> None:
    global op
    op = t.cast(ExtendedOperations, op)

    # Migrate each column, interpreting existing values as UTC
    for table, columns in TimestampColumns.items():
        for column in columns:
            # Use raw SQL to convert with proper UTC interpretation
            # The AT TIME ZONE 'UTC' tells PostgreSQL to treat the naive timestamp as UTC
            op.execute(
                text(f"""
                    ALTER TABLE {table}
                    ALTER COLUMN {column}
                    TYPE TIMESTAMP WITH TIME ZONE
                    USING {column} AT TIME ZONE 'UTC'
                """)
            )


def downgrade() -> None:
    global op
    op = t.cast(ExtendedOperations, op)

    # Revert to timestamp without time zone
    # Convert back by extracting the UTC time
    for table, columns in TimestampColumns.items():
        for column in columns:
            op.execute(
                text(f"""
                    ALTER TABLE {table}
                    ALTER COLUMN {column}
                    TYPE TIMESTAMP WITHOUT TIME ZONE
                    USING {column} AT TIME ZONE 'UTC'
                """)
            )
