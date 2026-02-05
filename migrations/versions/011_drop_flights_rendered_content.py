"""Drop rendered_content column from flights.

Revision ID: 011
Revises: 010
Create Date: 2026-02-05

The rendered content is now computed at response time from the template
source, feature_flags, and context already stored on each flight row.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "011_drop_rendered_content"
down_revision = "010_template_content_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("flights", "rendered_content")


def downgrade() -> None:
    from sqlalchemy.schema import Column
    from sqlalchemy.types import Text

    op.add_column("flights", Column("rendered_content", Text, nullable=True))
