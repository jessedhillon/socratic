"""Tools available to the assessment agent."""

import typing as t

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import InjectedToolCallId, StructuredTool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from .farewell import FarewellAgent, FarewellState
from .state import Conviviality


def make_end_assessment_tool(model: BaseChatModel) -> StructuredTool:
    """Create the end_assessment tool with a farewell subagent.

    The tool captures a compiled ``FarewellAgent`` graph so it can generate
    a spoken goodbye inline within the tool call. Tokens from the subagent's
    model call stream to TTS via the parent graph's ``astream_events``
    callback propagation.
    """
    farewell_agent = FarewellAgent(model)
    farewell_graph = farewell_agent.compile()

    def _end_assessment(
        tool_call_id: t.Annotated[str, InjectedToolCallId],
        messages: t.Annotated[list[BaseMessage], InjectedState("messages")],
        conviviality: t.Annotated[Conviviality, InjectedState("conviviality")],
        objective_title: t.Annotated[str, InjectedState("objective_title")],
        summary: str = "",
    ) -> Command[None]:
        """End the assessment session (sync path)."""
        ai_count = sum(1 for m in messages if isinstance(m, AIMessage))
        if ai_count <= 1:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=(
                                "The assessment has barely started. Continue exploring "
                                "the learner's understanding before ending."
                            ),
                            tool_call_id=tool_call_id,
                        )
                    ],
                },
            )

        conversational: list[BaseMessage] = [
            m for m in messages if isinstance(m, HumanMessage) or (isinstance(m, AIMessage) and not m.tool_calls)
        ]
        input_ids = {id(m) for m in conversational[-4:]}
        farewell_state = FarewellState(
            conviviality=conviviality,
            objective_title=objective_title,
            messages=conversational[-4:],
        )
        result = farewell_graph.invoke(farewell_state)
        farewell_msgs = [m for m in result["messages"] if id(m) not in input_ids]

        content = f"Assessment ended. Summary: {summary}" if summary else "Assessment ended."
        return Command(
            update={
                "assessment_complete": True,
                "messages": [
                    ToolMessage(content=content, tool_call_id=tool_call_id),
                    *farewell_msgs,
                ],
            },
        )

    async def _aend_assessment(
        tool_call_id: t.Annotated[str, InjectedToolCallId],
        messages: t.Annotated[list[BaseMessage], InjectedState("messages")],
        conviviality: t.Annotated[Conviviality, InjectedState("conviviality")],
        objective_title: t.Annotated[str, InjectedState("objective_title")],
        summary: str = "",
    ) -> Command[None]:
        """End the assessment session.

        Generates a farewell via a ``FarewellAgent`` subagent before
        terminating. The farewell tokens stream to TTS through the parent
        graph's ``astream_events`` callback propagation.
        """
        ai_count = sum(1 for m in messages if isinstance(m, AIMessage))
        if ai_count <= 1:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=(
                                "The assessment has barely started. Continue exploring "
                                "the learner's understanding before ending."
                            ),
                            tool_call_id=tool_call_id,
                        )
                    ],
                },
            )

        # Collect recent conversational turns for the farewell subagent,
        # excluding tool-call/response messages that would cause OpenAI
        # validation errors (every tool_calls AIMessage must be paired
        # with a ToolMessage response).
        conversational: list[BaseMessage] = [
            m for m in messages if isinstance(m, HumanMessage) or (isinstance(m, AIMessage) and not m.tool_calls)
        ]
        input_ids = {id(m) for m in conversational[-4:]}
        farewell_state = FarewellState(
            conviviality=conviviality,
            objective_title=objective_title,
            messages=conversational[-4:],
        )
        result = await farewell_graph.ainvoke(farewell_state)
        farewell_msgs = [m for m in result["messages"] if id(m) not in input_ids]

        content = f"Assessment ended. Summary: {summary}" if summary else "Assessment ended."
        return Command(
            update={
                "assessment_complete": True,
                "messages": [
                    ToolMessage(content=content, tool_call_id=tool_call_id),
                    *farewell_msgs,
                ],
            },
        )

    return StructuredTool.from_function(
        func=_end_assessment,
        coroutine=_aend_assessment,
        name="end_assessment",
        description=(
            "End the assessment. Call this when you have explored all rubric criteria "
            "sufficiently, or when the learner indicates they want to stop. You MUST call "
            "this tool to end the assessment — do not simply stop responding. "
            "A farewell will be spoken to the learner automatically."
        ),
    )
