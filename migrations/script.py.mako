"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
import typing as t

from alembic import op
from sqlalchemy import func as f
from sqlalchemy.schema import Column, ForeignKey
from sqlalchemy.types import DateTime, String
${imports if imports else ""}

from socratic.lib.sql import ExtendedOperations

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | t.Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | t.Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    global op
    op = t.cast(ExtendedOperations, op)
    ${upgrades or "pass"}


def downgrade() -> None:
    global op
    op = t.cast(ExtendedOperations, op)
    ${downgrades or "pass"}
