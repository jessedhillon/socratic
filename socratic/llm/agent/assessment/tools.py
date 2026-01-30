"""Tools available to the assessment agent."""

import typing as t

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import InjectedToolCallId, StructuredTool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command


def _end_assessment(
    tool_call_id: t.Annotated[str, InjectedToolCallId],
    messages: t.Annotated[list[BaseMessage], InjectedState("messages")],
    has_said_farewell: bool = False,
    summary: str = "",
) -> Command[None]:
    """End the assessment session."""
    # Reject if this is too early — only a greeting has been exchanged.
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

    # Reject if the agent hasn't said goodbye yet.
    if not has_said_farewell:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=(
                            "You must say goodbye to the learner before ending. "
                            "Thank them briefly, then call end_assessment again "
                            "with has_said_farewell=true."
                        ),
                        tool_call_id=tool_call_id,
                    )
                ],
            },
        )

    content = f"Assessment ended. Summary: {summary}" if summary else "Assessment ended."
    return Command(
        update={
            "assessment_complete": True,
            "messages": [ToolMessage(content=content, tool_call_id=tool_call_id)],
        },
    )


async def _aend_assessment(
    tool_call_id: t.Annotated[str, InjectedToolCallId],
    messages: t.Annotated[list[BaseMessage], InjectedState("messages")],
    has_said_farewell: bool = False,
    summary: str = "",
) -> Command[None]:
    """End the assessment session (async)."""
    return _end_assessment(
        tool_call_id=tool_call_id, messages=messages, has_said_farewell=has_said_farewell, summary=summary
    )


EndAssessmentTool = StructuredTool.from_function(
    func=_end_assessment,
    coroutine=_aend_assessment,
    name="end_assessment",
    description=(
        "End the assessment. Call this when you have explored all rubric criteria "
        "sufficiently, or when the learner indicates they want to stop. You MUST call "
        "this tool to end the assessment — do not simply stop responding. "
        "You must say goodbye to the learner BEFORE calling this tool, then set "
        "has_said_farewell=true. The call will be rejected if has_said_farewell is false."
    ),
)
