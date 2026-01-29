"""Assessment agent state schema.

Defines the typed state for the assessment agent. Fields fall into two
categories:

**Context** — set once when the assessment starts, immutable during execution.
These describe *what* the agent is assessing (objective, rubric, prompts).

**Dynamic** — updated during execution via tool calls. These track what the
agent has observed and whether it considers the assessment complete.
"""

from __future__ import annotations

import datetime
import enum

import pydantic as p
from langchain_core.messages import HumanMessage

from socratic.llm.agent.state import AgentState
from socratic.model.rubric import RubricCriterion


class CoverageLevel(enum.Enum):
    """How thoroughly a rubric criterion has been explored."""

    NotStarted = "not_started"
    Partial = "partial"
    Full = "full"


class CriterionCoverage(p.BaseModel):
    """Agent's recorded observations about a single rubric criterion."""

    criterion_id: str
    criterion_name: str
    coverage: CoverageLevel = CoverageLevel.NotStarted
    evidence: list[str] = p.Field(default_factory=list)


class AssessmentState(AgentState):
    """State for the assessment agent.

    The agent receives this state on every invocation. Context fields give it
    the assessment brief; dynamic fields give it situational awareness (via
    the status message rendered from these fields each turn).
    """

    # -- Context (set once at start) ----------------------------------------

    attempt_id: str
    objective_title: str
    objective_description: str
    rubric_criteria: list[RubricCriterion] = p.Field(default_factory=list[RubricCriterion])
    initial_prompts: list[str] = p.Field(default_factory=list)
    time_budget_minutes: int | None = None
    start_time: datetime.datetime | None = None

    # -- Dynamic (updated by tools during execution) ------------------------

    criteria_coverage: dict[str, CriterionCoverage] = p.Field(default_factory=dict)
    assessment_complete: bool = False

    @property
    def completed(self) -> bool:
        return self.assessment_complete

    @property
    def turn_count(self) -> int:
        """Number of human messages in the conversation."""
        return sum(1 for m in self.messages if isinstance(m, HumanMessage))

    @property
    def elapsed_minutes(self) -> float | None:
        """Minutes since assessment started, or None if not started."""
        if self.start_time is None:
            return None
        now = datetime.datetime.now(datetime.UTC)
        start = self.start_time.replace(tzinfo=datetime.UTC) if self.start_time.tzinfo is None else self.start_time
        return (now - start).total_seconds() / 60.0
