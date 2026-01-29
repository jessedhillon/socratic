"""Tools available to the assessment agent."""

from __future__ import annotations

from langchain_core.tools import BaseTool
from pydantic import Field


class EndAssessmentTool(BaseTool):
    """Signal that the assessment is complete.

    The agent calls this when it has gathered sufficient evidence across
    all rubric criteria, or when circumstances warrant ending early.
    """

    name: str = "end_assessment"
    description: str = (
        "End the assessment. Call this when you have explored all rubric criteria "
        "sufficiently, or when you need to end the assessment early. You MUST call "
        "this tool to end the assessment — do not simply stop responding."
    )
    summary: str = Field(default="", description="Brief summary of what was covered in the assessment.")

    def _run(self, summary: str = "") -> str:
        return f"Assessment ended. Summary: {summary}" if summary else "Assessment ended."

    async def _arun(self, summary: str = "") -> str:
        return self._run(summary)
