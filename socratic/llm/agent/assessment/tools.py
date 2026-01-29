"""Tools available to the assessment agent."""

from __future__ import annotations

import typing as t

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, InjectedToolCallId
from langgraph.types import Command


class EndAssessmentTool(BaseTool):
    """Signal that the assessment is complete.

    The agent calls this when it has gathered sufficient evidence across
    all rubric criteria, or when circumstances warrant ending early.

    Returns a ``Command`` that sets ``assessment_complete`` on the graph
    state, so the agent's exit predicate fires without needing a custom
    tool-node override.
    """

    name: str = "end_assessment"
    description: str = (
        "End the assessment. Call this when you have explored all rubric criteria "
        "sufficiently, or when you need to end the assessment early. You MUST call "
        "this tool to end the assessment — do not simply stop responding."
    )

    def _run(
        self,
        summary: str = "",
        tool_call_id: t.Annotated[str, InjectedToolCallId] = "",
    ) -> Command[None]:
        content = f"Assessment ended. Summary: {summary}" if summary else "Assessment ended."
        return Command(
            update={
                "assessment_complete": True,
                "messages": [ToolMessage(content=content, tool_call_id=tool_call_id)],
            },
        )

    async def _arun(
        self,
        summary: str = "",
        tool_call_id: t.Annotated[str, InjectedToolCallId] = "",
    ) -> Command[None]:
        return self._run(summary, tool_call_id)
