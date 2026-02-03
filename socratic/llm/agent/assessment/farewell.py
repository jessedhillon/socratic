"""Farewell subagent — generates a closing message when the assessment ends.

Invoked inline by the ``end_assessment`` tool to produce a spoken farewell
within the tool call itself. The agent's model tokens stream to TTS through
the parent graph's ``astream_events`` callback propagation (LangGraph <1.0)
or ``subgraphs=True`` (LangGraph >=1.0).
"""

from __future__ import annotations

import typing as t

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage

from socratic.llm.agent.base import BaseAgent
from socratic.llm.agent.state import AgentState

from .state import Conviviality


class FarewellState(AgentState):
    """State for the farewell subagent.

    Populated from the parent assessment's state when the tool constructs
    the subagent.
    """

    conviviality: Conviviality = Conviviality.Conversational
    objective_title: str = ""


class FarewellAgent(BaseAgent[FarewellState]):
    """Single-turn agent that generates a farewell message.

    Has no tools — the graph runs ``start → status → model → end``,
    producing exactly one AI message (the farewell).
    """

    name: str = "farewell"

    def __init__(self, model: BaseChatModel) -> None:
        super().__init__(model)

    def system_prompt(self, state: FarewellState) -> SystemMessage:
        tone = _tone_instruction(state.conviviality)
        return SystemMessage(
            content=(
                f"You are wrapping up a conversation about {state.objective_title}. "
                f"{tone} "
                "Say a brief farewell to the learner — thank them for their time "
                "and wish them well. Keep it to 1-2 short sentences. "
                "Do not ask any questions or introduce new topics."
            ),
        )


def _tone_instruction(conviviality: Conviviality) -> str:
    match conviviality:
        case Conviviality.Formal:
            return "Keep the farewell brief and professional."
        case Conviviality.Professional:
            return "Be polite and measured."
        case Conviviality.Conversational:
            return "Be warm and natural."
        case Conviviality.Collegial:
            return "Be genuinely warm and appreciative."
        case _:
            t.assert_never(conviviality)
