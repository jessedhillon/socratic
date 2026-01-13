"""Drop weight column from rubric_criteria

With the migration to proficiency levels, evaluation is qualitative
rather than score-based. Weight is no longer meaningful.

Revision ID: 005_drop_weight
Revises: 004_proficiency_levels
Create Date: 2026-01-12

"""

import typing as t

from alembic import op

from socratic.lib.sql import ExtendedOperations

# revision identifiers, used by Alembic.
revision: str = "005_drop_weight"
down_revision: str | None = "004_proficiency_levels"
branch_labels: str | t.Sequence[str] | None = None
depends_on: str | t.Sequence[str] | None = None


def upgrade() -> None:
    global op
    op = t.cast(ExtendedOperations, op)

    op.drop_column("rubric_criteria", "weight")


def downgrade() -> None:
    global op
    op = t.cast(ExtendedOperations, op)

    import decimal

    from sqlalchemy.schema import Column
    from sqlalchemy.types import Numeric

    op.add_column(
        "rubric_criteria",
        Column("weight", Numeric(4, 2), server_default="1.0", default=decimal.Decimal("1.0")),
    )
