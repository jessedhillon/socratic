"""PostgreSQL checkpointer for LangGraph state persistence."""

from __future__ import annotations

import typing as t
import uuid
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from socratic import storage
from socratic.core import di
from socratic.model import AttemptID
from socratic.storage import agent_state as agent_state_storage

from .state import AgentState, InterviewPhase


class PostgresCheckpointer:
    """Checkpointer that persists LangGraph state to PostgreSQL.

    This allows assessment conversations to span multiple HTTP requests
    by loading and saving state from the database.
    """

    @di.inject
    def get(
        self, attempt_id: AttemptID, session: storage.Session = di.Provide["storage.persistent.session"]
    ) -> AgentState | None:
        """Load agent state from database."""
        with session.begin():
            record = agent_state_storage.get(attempt_id, session=session)
            if record is None:
                return None
            return self._deserialize_state(record.checkpoint_data)

    def put(
        self,
        attempt_id: AttemptID,
        state: AgentState,
        session: storage.Session = di.Provide["storage.persistent.session"],
    ) -> None:
        """Save agent state to database."""
        with session.begin():
            checkpoint_data = self._serialize_state(state)
            thread_id = state.get("attempt_id", str(uuid.uuid4()))
            agent_state_storage.upsert(
                attempt_id=attempt_id,
                checkpoint_data=checkpoint_data,
                thread_id=thread_id,
                session=session,
            )

    def delete(
        self, attempt_id: AttemptID, session: storage.Session = di.Provide["storage.persistent.session"]
    ) -> bool:
        """Delete agent state from database."""
        with session.begin():
            return agent_state_storage.delete(attempt_id, session=session)

    @di.inject
    async def aget(
        self, attempt_id: AttemptID, session: storage.AsyncSession = di.Provide["storage.persistent.async_session"]
    ) -> AgentState | None:
        """Load agent state from database (async)."""
        async with session.begin():
            record = await agent_state_storage.aget(attempt_id, session=session)
            if record is None:
                return None
            return self._deserialize_state(record.checkpoint_data)

    @di.inject
    async def aput(
        self,
        attempt_id: AttemptID,
        state: AgentState,
        session: storage.AsyncSession = di.Provide["storage.persistent.async_session"],
    ) -> None:
        """Save agent state to database (async)."""
        async with session.begin():
            checkpoint_data = self._serialize_state(state)
            thread_id = state.get("attempt_id", str(uuid.uuid4()))
            await agent_state_storage.aupsert(
                attempt_id=attempt_id,
                checkpoint_data=checkpoint_data,
                thread_id=thread_id,
                session=session,
            )

    def _serialize_state(self, state: AgentState) -> dict[str, t.Any]:
        """Serialize AgentState to JSON-compatible dict."""
        data: dict[str, t.Any] = {}

        for key, value in state.items():
            if key == "messages":
                data[key] = [self._serialize_message(m) for m in value]
            elif key == "phase" and isinstance(value, InterviewPhase):
                data[key] = value.value
            elif key == "start_time" and isinstance(value, datetime):
                # Serialize datetime to ISO format string
                data[key] = value.isoformat()
            else:
                data[key] = value

        return data

    def _deserialize_state(self, data: dict[str, t.Any]) -> AgentState:
        """Deserialize JSON dict to AgentState."""
        state: dict[str, t.Any] = {}

        for key, value in data.items():
            if key == "messages":
                state[key] = [self._deserialize_message(m) for m in value]
            elif key == "phase" and value is not None:
                state[key] = InterviewPhase(value)
            elif key == "start_time" and value is not None:
                state[key] = self._parse_datetime(value)
            else:
                state[key] = value

        return state

    def _parse_datetime(self, value: t.Any) -> datetime | None:
        """Parse a datetime value from JSON serialization.

        Handles both datetime objects (already parsed) and ISO format strings.
        """
        if value is None:
            return None

        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            try:
                if value.endswith("Z"):
                    return datetime.fromisoformat(value.replace("Z", "+00:00"))
                elif "+" in value or value.count("-") > 2:
                    return datetime.fromisoformat(value)
                else:
                    # Naive datetime string - assume UTC
                    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
            except ValueError:
                return None

        return None

    def _serialize_message(self, message: BaseMessage) -> dict[str, t.Any]:
        """Serialize a LangChain message to JSON."""
        return {
            "type": message.__class__.__name__,
            "content": message.content,
        }

    def _deserialize_message(self, data: dict[str, t.Any]) -> BaseMessage:
        """Deserialize JSON to a LangChain message."""
        msg_type = data.get("type", "HumanMessage")
        content = data.get("content", "")

        if msg_type == "AIMessage":
            return AIMessage(content=content)
        elif msg_type == "SystemMessage":
            return SystemMessage(content=content)
        else:
            return HumanMessage(content=content)
