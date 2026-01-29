"""Base state schema for LangGraph agents."""

from __future__ import annotations

import typing as t

import pydantic as p
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class AgentState(p.BaseModel):
    """Base state for all agents.

    Provides the core message history and a status slot that is dynamically
    rendered before each model call. Subclasses add domain-specific fields.

    The ``status`` field is ephemeral — it is rebuilt by the status node each
    iteration and is *not* part of the persisted conversation history. It is
    appended to the LLM input so the model can reason about current state.
    """

    messages: t.Annotated[list[BaseMessage], add_messages] = p.Field(default_factory=list)
    status: BaseMessage | None = None

    model_config = p.ConfigDict(arbitrary_types_allowed=True)

    @property
    def completed(self) -> bool:
        """Override in subclasses to signal the agent should terminate."""
        return False
