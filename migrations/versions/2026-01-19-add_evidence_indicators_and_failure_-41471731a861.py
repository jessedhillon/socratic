"""add evidence_indicators and failure_modes to rubric_criteria

Revision ID: 41471731a861
Revises: 007_word_timings
Create Date: 2026-01-19 12:38:10.324881

"""

import typing as t

import sqlalchemy as sqla
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from socratic.lib.sql import ExtendedOperations

# revision identifiers, used by Alembic.
revision: str = "41471731a861"
down_revision: str | None = "007_word_timings"
branch_labels: str | t.Sequence[str] | None = None
depends_on: str | t.Sequence[str] | None = None


def upgrade() -> None:
    global op
    op = t.cast(ExtendedOperations, op)
    op.add_column(
        "rubric_criteria",
        sqla.Column("evidence_indicators", JSONB, nullable=False, server_default="[]"),
    )
    op.add_column(
        "rubric_criteria",
        sqla.Column("failure_modes", JSONB, nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    global op
    op = t.cast(ExtendedOperations, op)
    op.drop_column("rubric_criteria", "evidence_indicators")
    op.drop_column("rubric_criteria", "failure_modes")
