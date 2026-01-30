"""Tools available to the assessment agent."""

import typing as t

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import InjectedToolCallId, StructuredTool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command


def _has_spoken_content(msg: AIMessage) -> bool:
    """Check whether an AI message contains text (not just tool calls)."""
    content: t.Any = msg.content
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return any(  # pyright: ignore [reportUnknownArgumentType]
            (isinstance(block, str) and block.strip())
            or (
                isinstance(block, dict) and block.get("type") == "text" and str(block.get("text", "")).strip()  # pyright: ignore [reportUnknownArgumentType]
            )
            for block in content  # pyright: ignore [reportUnknownVariableType]
        )
    return False


def _end_assessment(
    tool_call_id: t.Annotated[str, InjectedToolCallId],
    messages: t.Annotated[list[BaseMessage], InjectedState("messages")],
    summary: str = "",
) -> Command[None]:
    """End the assessment session."""
    # Find the last AI message — this is the one that invoked us.
    last_ai: AIMessage | None = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            last_ai = msg
            break

    # Reject if the model didn't include farewell text alongside the tool call.
    if last_ai is not None and not _has_spoken_content(last_ai):
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=(
                            "You must say something to the learner before ending — "
                            "thank them briefly and then call end_assessment again."
                        ),
                        tool_call_id=tool_call_id,
                    )
                ],
            },
        )

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
    summary: str = "",
) -> Command[None]:
    """End the assessment session (async)."""
    return _end_assessment(tool_call_id=tool_call_id, messages=messages, summary=summary)


EndAssessmentTool = StructuredTool.from_function(
    func=_end_assessment,
    coroutine=_aend_assessment,
    name="end_assessment",
    description=(
        "End the assessment. Call this when you have explored all rubric criteria "
        "sufficiently, or when you need to end the assessment early. You MUST call "
        "this tool to end the assessment — do not simply stop responding."
    ),
)
