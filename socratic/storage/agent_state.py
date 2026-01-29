"""Storage functions for agent states (LangGraph checkpoints)."""

from __future__ import annotations

import datetime
import typing as t

import pydantic as p
import sqlalchemy as sqla
from sqlalchemy.dialects.postgresql import insert

from socratic.core import di
from socratic.model import AttemptID

from . import AsyncSession, Session
from .table import agent_states


class AgentStateRecord(p.BaseModel):
    """Agent state record from database."""

    attempt_id: AttemptID
    checkpoint_data: dict[str, t.Any]
    thread_id: str
    update_time: datetime.datetime


def get(
    attempt_id: AttemptID,
    *,
    session: Session = di.Provide["storage.persistent.session"],
) -> AgentStateRecord | None:
    """Get agent state for an attempt."""
    stmt = sqla.select(agent_states.__table__).where(agent_states.attempt_id == attempt_id)
    row = session.execute(stmt).mappings().one_or_none()
    return AgentStateRecord(**row) if row else None


def upsert(
    attempt_id: AttemptID,
    *,
    checkpoint_data: dict[str, t.Any],
    thread_id: str,
    session: Session = di.Provide["storage.persistent.session"],
) -> AgentStateRecord:
    """Create or update agent state for an attempt.

    Uses PostgreSQL upsert to handle concurrent updates.
    """
    stmt = insert(agent_states).values(
        attempt_id=attempt_id,
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
    result = get(attempt_id, session=session)
    assert result is not None
    return result


def delete(
    attempt_id: AttemptID,
    *,
    session: Session = di.Provide["storage.persistent.session"],
) -> bool:
    """Delete agent state for an attempt.

    Returns:
        True if deleted, False if not found
    """
    stmt = sqla.delete(agent_states).where(agent_states.attempt_id == attempt_id)
    result = session.execute(stmt)
    return bool(result.rowcount)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownArgumentType]


# Async variants for use in the LiveKit agent event loop


async def aget(
    attempt_id: AttemptID,
    *,
    session: AsyncSession,
) -> AgentStateRecord | None:
    """Get agent state for an attempt (async)."""
    stmt = sqla.select(agent_states.__table__).where(agent_states.attempt_id == attempt_id)
    row = (await session.execute(stmt)).mappings().one_or_none()
    return AgentStateRecord(**row) if row else None


async def aupsert(
    attempt_id: AttemptID,
    *,
    checkpoint_data: dict[str, t.Any],
    thread_id: str,
    session: AsyncSession,
) -> AgentStateRecord:
    """Create or update agent state for an attempt (async)."""
    stmt = insert(agent_states).values(
        attempt_id=attempt_id,
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
    await session.execute(stmt)
    await session.flush()
    result = await aget(attempt_id, session=session)
    assert result is not None
    return result
