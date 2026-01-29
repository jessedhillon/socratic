"""Assessment agent — conducts Socratic interviews via a single-prompt design.

Behavior emerges from the system prompt and per-turn status message rather
than hard-coded phase transitions. The agent decides when to probe, move on,
and end the assessment based on its reasoning about the conversation and
the rubric coverage shown in the status message.
"""

from __future__ import annotations

import typing as t

import jinja2
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from socratic.llm.agent.base import BaseAgent

from .state import AssessmentState
from .status import render_status
from .tools import EndAssessmentTool


class AssessmentAgent(BaseAgent[AssessmentState]):
    """Socratic assessment interviewer.

    Uses a single system prompt with per-turn status updates. The agent
    works through rubric criteria using educator-provided prompts as starting
    points, probes for depth, and decides when to end the assessment.

    The ``end_assessment`` tool is the agent's only way to terminate — it must
    explicitly decide the assessment is complete.
    """

    name: str = "assessment"

    def __init__(
        self,
        model: BaseChatModel,
        *,
        env: jinja2.Environment,
        tools: t.Sequence[BaseTool] | None = None,
    ) -> None:
        all_tools: list[BaseTool] = [EndAssessmentTool]
        if tools:
            all_tools.extend(tools)
        self.env = env
        super().__init__(model, tools=all_tools)

    def system_prompt(self, state: AssessmentState) -> SystemMessage:
        """Render the system prompt with objective and rubric context."""
        template = self.env.get_template("agent/assessment_system.j2")
        content = template.render(
            objective_title=state.objective_title,
            objective_description=state.objective_description,
            rubric_criteria=state.rubric_criteria,
            initial_prompts=state.initial_prompts,
            time_budget_minutes=state.time_budget_minutes,
        )
        return SystemMessage(content=content)

    def update_status(self, state: AssessmentState) -> dict[str, t.Any]:
        """Render a fresh status message with coverage and progress."""
        content = render_status(state, self.env)
        return {"status": HumanMessage(content=content)}

    def exit(self, state: AssessmentState) -> bool:
        """Check if the agent has ended the assessment."""
        return state.assessment_complete
