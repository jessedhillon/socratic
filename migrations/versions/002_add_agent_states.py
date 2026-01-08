"""Add agent_states table for LangGraph checkpoints

Revision ID: 002_agent_states
Revises: 001_initial
Create Date: 2026-01-08

"""

import typing as t

from alembic import op
from sqlalchemy import func as f
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.schema import Column, ForeignKey
from sqlalchemy.types import DateTime, String

from socratic.lib.sql import ExtendedOperations

# revision identifiers, used by Alembic.
revision: str = "002_agent_states"
down_revision: str | None = "001_initial"
branch_labels: str | t.Sequence[str] | None = None
depends_on: str | t.Sequence[str] | None = None


def upgrade() -> None:
    global op
    op = t.cast(ExtendedOperations, op)

    op.create_table(
        "agent_states",
        Column(
            "attempt_id",
            String(22),
            ForeignKey("assessment_attempts.attempt_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        Column("checkpoint_data", JSONB, nullable=False),
        Column("thread_id", String, nullable=False),
        Column("update_time", DateTime, server_default=f.now(), onupdate=f.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("agent_states")
