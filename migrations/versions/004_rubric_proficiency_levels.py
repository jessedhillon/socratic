"""Migrate rubric criteria from evidence indicators to proficiency descriptions

Revision ID: 004_proficiency_levels
Revises: 003_password_required
Create Date: 2026-01-12

"""

import typing as t

from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

from socratic.lib.sql import ExtendedOperations

# revision identifiers, used by Alembic.
revision: str = "004_proficiency_levels"
down_revision: str | None = "003_password_required"
branch_labels: str | t.Sequence[str] | None = None
depends_on: str | t.Sequence[str] | None = None


def upgrade() -> None:
    global op
    op = t.cast(ExtendedOperations, op)

    from sqlalchemy.schema import Column

    # Add new proficiency_levels column
    op.add_column("rubric_criteria", Column("proficiency_levels", JSONB, server_default="[]"))

    # Migrate data from grade_thresholds to proficiency_levels
    # grade_thresholds has: [{grade, description, min_evidence_count}, ...]
    # proficiency_levels needs: [{grade, description}, ...]
    op.execute(
        text(
            """
            UPDATE rubric_criteria
            SET proficiency_levels = (
                SELECT COALESCE(
                    jsonb_agg(
                        jsonb_build_object(
                            'grade', elem->>'grade',
                            'description', elem->>'description'
                        )
                    ),
                    '[]'::jsonb
                )
                FROM jsonb_array_elements(grade_thresholds) AS elem
            )
            WHERE jsonb_array_length(grade_thresholds) > 0
            """
        )
    )

    # Drop old columns
    op.drop_column("rubric_criteria", "evidence_indicators")
    op.drop_column("rubric_criteria", "failure_modes")
    op.drop_column("rubric_criteria", "grade_thresholds")


def downgrade() -> None:
    global op
    op = t.cast(ExtendedOperations, op)

    from sqlalchemy.dialects.postgresql import ARRAY
    from sqlalchemy.schema import Column
    from sqlalchemy.types import String

    # Restore old columns
    op.add_column("rubric_criteria", Column("evidence_indicators", ARRAY(String), server_default="{}"))
    op.add_column("rubric_criteria", Column("failure_modes", JSONB, server_default="[]"))
    op.add_column("rubric_criteria", Column("grade_thresholds", JSONB, server_default="[]"))

    # Migrate data back from proficiency_levels to grade_thresholds
    op.execute(
        text(
            """
            UPDATE rubric_criteria
            SET grade_thresholds = (
                SELECT COALESCE(
                    jsonb_agg(
                        jsonb_build_object(
                            'grade', elem->>'grade',
                            'description', elem->>'description',
                            'min_evidence_count', NULL
                        )
                    ),
                    '[]'::jsonb
                )
                FROM jsonb_array_elements(proficiency_levels) AS elem
            )
            WHERE jsonb_array_length(proficiency_levels) > 0
            """
        )
    )

    # Drop new column
    op.drop_column("rubric_criteria", "proficiency_levels")
