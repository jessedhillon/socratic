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
from socratic.model import FlightID
from socratic.model.rubric import ProficiencyLevel


class AssessmentCriterion(p.BaseModel):
    """Rubric criterion as seen by the assessment agent.

    Carries only the fields needed at runtime — ``objective_id`` and other
    storage-level concerns are stripped before the agent session starts.
    """

    criterion_id: str
    name: str
    description: str
    proficiency_levels: list[ProficiencyLevel] = p.Field(default_factory=list[ProficiencyLevel])


class Conviviality(enum.Enum):
    """How warm and conversational the interviewer should be."""

    Formal = "formal"
    Professional = "professional"
    Conversational = "conversational"
    Collegial = "collegial"


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
    flight_id: FlightID | None = None
    objective_title: str
    objective_description: str
    rubric_criteria: list[AssessmentCriterion] = p.Field(default_factory=list[AssessmentCriterion])
    initial_prompts: list[str] = p.Field(default_factory=list)
    conviviality: Conviviality = Conviviality.Conversational
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
