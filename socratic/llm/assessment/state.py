"""Agent state schema for the assessment interview."""

from __future__ import annotations

import enum
import typing as t
from typing import TypedDict


class InterviewPhase(enum.Enum):
    """Phases of the Socratic interview."""

    Orientation = "orientation"
    PrimaryPrompts = "primary_prompts"
    DynamicProbing = "dynamic_probing"
    Extension = "extension"
    Closure = "closure"
    Complete = "complete"


class RubricCriterionContext(TypedDict):
    """Serialized rubric criterion for agent context."""

    criterion_id: str
    name: str
    description: str
    evidence_indicators: list[str]
    failure_modes: list[str]


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
- initial_prompts: list[str] - Educator-defined questions
- challenge_prompts: list[str] - Additional probing questions
- extension_policy: str - "allowed", "disallowed", or "conditional"
- rubric_criteria: list[RubricCriterionContext] - Serialized criteria
- current_prompt_index: int - Progress through prompts
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
