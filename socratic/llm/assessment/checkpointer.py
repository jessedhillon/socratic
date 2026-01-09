"""PostgreSQL checkpointer for LangGraph state persistence."""

from __future__ import annotations

import typing as t
import uuid

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
            session.commit()

    def delete(
        self, attempt_id: AttemptID, session: storage.Session = di.Provide["storage.persistent.session"]
    ) -> bool:
        """Delete agent state from database."""
        with session.begin():
            result = agent_state_storage.delete(attempt_id, session=session)
            session.commit()
            return result

    def _serialize_state(self, state: AgentState) -> dict[str, t.Any]:
        """Serialize AgentState to JSON-compatible dict."""
        data: dict[str, t.Any] = {}

        for key, value in state.items():
            if key == "messages":
                data[key] = [self._serialize_message(m) for m in value]
            elif key == "phase" and isinstance(value, InterviewPhase):
                data[key] = value.value
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
            else:
                state[key] = value

        return state

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
