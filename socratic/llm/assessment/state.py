"""Agent state schema for the assessment interview."""

from __future__ import annotations

import enum
import typing as t
from datetime import datetime, timezone
from typing import TypedDict


class InterviewPhase(enum.Enum):
    """Phases of the Socratic interview."""

    Orientation = "orientation"
    PrimaryPrompts = "primary_prompts"
    DynamicProbing = "dynamic_probing"
    Extension = "extension"
    Closure = "closure"
    Complete = "complete"


class CoverageLevel(enum.Enum):
    """Coverage level for a rubric criterion."""

    NotStarted = "not_started"
    PartiallyExplored = "partially_explored"
    FullyExplored = "fully_explored"


GradeLevel = t.Literal["S", "A", "C", "F"]
"""Valid grade levels for proficiency assessment."""


class ProficiencyLevelContext(TypedDict):
    """Serialized proficiency level for agent context."""

    grade: GradeLevel
    description: str  # What this grade level looks like


class RubricCriterionContext(TypedDict):
    """Serialized rubric criterion for agent context.

    Uses proficiency descriptions rather than evidence indicators.
    See docs/assessment-model.md for rationale.
    """

    criterion_id: str
    name: str
    description: str
    proficiency_levels: list[ProficiencyLevelContext]


class CriteriaCoverageEntry(TypedDict):
    """Tracking entry for criterion coverage during assessment."""

    criterion_id: str
    criterion_name: str
    coverage_level: str  # CoverageLevel.value
    evidence_found: list[str]  # Specific evidence observed
    last_touched_turn: int  # Turn number when last explored


class PacingStatus(TypedDict):
    """Current pacing information for the assessment."""

    elapsed_minutes: float
    estimated_total_minutes: int
    remaining_minutes: float
    percent_elapsed: float
    pace: str  # "ahead", "on_track", "behind", or "overtime"


def calculate_pacing_status(
    start_time: datetime | None,
    estimated_minutes: int | None,
) -> PacingStatus | None:
    """Calculate current pacing status for the assessment.

    Args:
        start_time: When the assessment started (UTC)
        estimated_minutes: Expected total duration

    Returns:
        PacingStatus dict or None if start_time is not set
    """
    if start_time is None:
        return None

    estimated = estimated_minutes or 15  # Default 15 minutes
    now = datetime.now(timezone.utc)
    # Handle both naive and aware datetimes - assume naive is UTC
    if start_time.tzinfo is None:
        start_utc = start_time.replace(tzinfo=timezone.utc)
    else:
        start_utc = start_time
    elapsed = (now - start_utc).total_seconds() / 60.0
    remaining = max(0, estimated - elapsed)
    percent = min(100.0, (elapsed / estimated) * 100) if estimated > 0 else 100.0

    # Determine pace label
    if elapsed > estimated:
        pace = "overtime"
    elif percent > 80:
        pace = "behind"
    elif percent < 40:
        pace = "ahead"
    else:
        pace = "on_track"

    return PacingStatus(
        elapsed_minutes=round(elapsed, 1),
        estimated_total_minutes=estimated,
        remaining_minutes=round(remaining, 1),
        percent_elapsed=round(percent, 1),
        pace=pace,
    )


# Using a regular dict type alias for more flexible state handling
# TypedDict is too strict for LangGraph's dynamic state updates
AgentState = dict[str, t.Any]
"""State schema for the assessment LangGraph agent.

Expected keys:
- messages: list[BaseMessage] - Conversation history
- phase: InterviewPhase | None - Current interview phase
- attempt_id: str - Attempt identifier
- objective_id: str - Objective identifier
- objective_title: str - Title for display
- objective_description: str - Full description
- scope_boundaries: str | None - What's not included
- time_expectation_minutes: int | None - Expected duration
- start_time: datetime | None - When the assessment started (UTC)
- initial_prompts: list[str] - Educator-defined questions
- challenge_prompts: list[str] - Additional probing questions
- extension_policy: str - "allowed", "disallowed", or "conditional"
- rubric_criteria: list[RubricCriterionContext] - Serialized criteria
- criteria_coverage: dict[str, CriteriaCoverageEntry] - Tracking coverage per criterion
- current_prompt_index: int - Progress through prompts
- current_turn: int - Turn counter for tracking
- probing_depth: int - Follow-up depth for current prompt
- max_probing_depth: int - Maximum follow-ups allowed
- learner_consent_confirmed: bool - Whether consent was given
- detected_ambiguity: bool - Flag from analysis
- detected_inconsistency: bool - Flag from analysis
- detected_evasion: bool - Flag from analysis
- ambiguous_phrase: str | None - Extracted for probing
- earlier_point: str | None - For inconsistency probing
- current_point: str | None - For inconsistency probing
- probing_topic: str | None - Current topic being probed
- key_points_summary: list[str] - For closure
"""
