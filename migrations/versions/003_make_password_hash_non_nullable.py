"""Make password_hash non-nullable

Revision ID: 003_password_required
Revises: 002_agent_states
Create Date: 2026-01-10

"""

import typing as t

import bcrypt
from alembic import op
from sqlalchemy import text
from sqlalchemy.types import String

from socratic.lib.sql import ExtendedOperations

# revision identifiers, used by Alembic.
revision: str = "003_password_required"
down_revision: str | None = "002_agent_states"
branch_labels: str | t.Sequence[str] | None = None
depends_on: str | t.Sequence[str] | None = None


def upgrade() -> None:
    global op
    op = t.cast(ExtendedOperations, op)

    # Set default password for any users with NULL password_hash
    default_hash = bcrypt.hashpw(b"password", bcrypt.gensalt()).decode("utf-8")
    op.execute(text("UPDATE users SET password_hash = :hash WHERE password_hash IS NULL").bindparams(hash=default_hash))

    op.alter_column("users", "password_hash", existing_type=String, nullable=False)


def downgrade() -> None:
    global op
    op = t.cast(ExtendedOperations, op)

    op.alter_column("users", "password_hash", existing_type=String, nullable=True)
