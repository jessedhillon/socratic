"""Storage functions for agent states (LangGraph checkpoints)."""

from __future__ import annotations

import datetime
import typing as t

from pydantic import BaseModel
from sqlalchemy import select

from socratic.core import di
from socratic.model import AttemptID

from . import Session
from .table import agent_states


class AgentStateRecord(BaseModel):
    """Agent state record from database."""

    attempt_id: AttemptID
    checkpoint_data: dict[str, t.Any]
    thread_id: str
    update_time: datetime.datetime


def get(
    attempt_id: AttemptID,
    session: Session = di.Provide["storage.persistent.session"],
) -> AgentStateRecord | None:
    """Get agent state for an attempt."""
    stmt = select(agent_states.__table__).where(agent_states.attempt_id == attempt_id)
    row = session.execute(stmt).mappings().one_or_none()
    return AgentStateRecord(**row) if row else None


def upsert(
    attempt_id: AttemptID,
    checkpoint_data: dict[str, t.Any],
    thread_id: str,
    session: Session = di.Provide["storage.persistent.session"],
) -> AgentStateRecord:
    """Create or update agent state for an attempt.

    Uses PostgreSQL upsert to handle concurrent updates.
    """
    from sqlalchemy.dialects.postgresql import insert

    stmt = insert(agent_states).values(
        attempt_id=str(attempt_id),
        checkpoint_data=checkpoint_data,
        thread_id=thread_id,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["attempt_id"],
        set_={
            "checkpoint_data": stmt.excluded.checkpoint_data,
            "thread_id": stmt.excluded.thread_id,
            "update_time": datetime.datetime.now(datetime.UTC),
        },
    )
    session.execute(stmt)
    session.flush()
    return get(attempt_id, session=session)  # type: ignore


def delete(
    attempt_id: AttemptID,
    session: Session = di.Provide["storage.persistent.session"],
) -> bool:
    """Delete agent state for an attempt."""
    stmt = select(agent_states).where(agent_states.attempt_id == attempt_id)
    state = session.execute(stmt).scalar_one_or_none()
    if state is None:
        return False
    session.delete(state)
    session.flush()
    return True
