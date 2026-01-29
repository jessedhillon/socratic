"""Tools available to the assessment agent."""

import typing as t

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, StructuredTool
from langgraph.types import Command


def _end_assessment(
    tool_call_id: t.Annotated[str, InjectedToolCallId],
    summary: str = "",
) -> Command[None]:
    """End the assessment session."""
    content = f"Assessment ended. Summary: {summary}" if summary else "Assessment ended."
    return Command(
        update={
            "assessment_complete": True,
            "messages": [ToolMessage(content=content, tool_call_id=tool_call_id)],
        },
    )


async def _aend_assessment(
    tool_call_id: t.Annotated[str, InjectedToolCallId],
    summary: str = "",
) -> Command[None]:
    """End the assessment session (async)."""
    return _end_assessment(tool_call_id=tool_call_id, summary=summary)


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
