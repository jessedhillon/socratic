"""Add versioning to survey schemas.

Revision ID: 012_survey_schema_versioning
Revises: 011_drop_rendered_content
Create Date: 2026-02-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012_survey_schema_versioning"
down_revision: str | None = "011_drop_rendered_content"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add version column with default 1
    op.add_column(
        "survey_schemas",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )

    # Add dimensions_hash column
    op.add_column(
        "survey_schemas",
        sa.Column("dimensions_hash", sa.String(length=64), nullable=False, server_default=""),
    )

    # Drop the unique constraint on name alone
    op.drop_constraint("uq_survey_schemas_name", "survey_schemas", type_="unique")

    # Add unique constraint on (name, version)
    op.create_unique_constraint(
        "uq_survey_schemas_name_version",
        "survey_schemas",
        ["name", "version"],
    )

    # Remove server defaults after initial data is set
    op.alter_column("survey_schemas", "version", server_default=None)
    op.alter_column("survey_schemas", "dimensions_hash", server_default=None)


def downgrade() -> None:
    # Drop the composite unique constraint
    op.drop_constraint("uq_survey_schemas_name_version", "survey_schemas", type_="unique")

    # Restore unique constraint on name alone
    op.create_unique_constraint("survey_schemas_name_key", "survey_schemas", ["name"])

    # Drop the new columns
    op.drop_column("survey_schemas", "dimensions_hash")
    op.drop_column("survey_schemas", "version")
