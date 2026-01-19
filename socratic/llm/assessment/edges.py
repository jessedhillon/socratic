"""Conditional edge functions for graph routing."""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import HumanMessage

from .nodes import get_content_str
from .state import AgentState, InterviewPhase


def check_consent(state: AgentState) -> Literal["primary_prompts", "closure"]:
    """Check if learner confirmed consent after orientation.

    Routes to primary_prompts if consent given, closure if declined.
    """
    if state.get("learner_consent_confirmed", False):
        return "primary_prompts"

    # Check the last human message for consent indicators
    messages = state.get("messages", [])
    learner_messages = [m for m in messages if isinstance(m, HumanMessage)]

    if not learner_messages:
        # No response yet, stay in orientation
        return "primary_prompts"  # Default to continuing

    last_message = get_content_str(learner_messages[-1].content).lower()

    # Simple keyword matching for consent
    consent_keywords = ["yes", "ready", "let's go", "begin", "start", "okay", "ok", "sure"]
    decline_keywords = ["no", "not ready", "stop", "cancel", "quit"]

    for keyword in consent_keywords:
        if keyword in last_message:
            return "primary_prompts"

    for keyword in decline_keywords:
        if keyword in last_message:
            return "closure"

    # Default to continuing if unclear
    return "primary_prompts"


def should_probe(state: AgentState) -> Literal["dynamic_probing", "check_more_prompts"]:
    """Determine if follow-up probing is needed based on response analysis.

    Routes to dynamic_probing if issues detected and within depth limit.
    """
    detected_ambiguity = state.get("detected_ambiguity", False)
    detected_inconsistency = state.get("detected_inconsistency", False)
    detected_evasion = state.get("detected_evasion", False)
    probing_depth = state.get("probing_depth", 0)
    max_probing_depth = state.get("max_probing_depth", 3)

    needs_probing = detected_ambiguity or detected_inconsistency or detected_evasion
    within_limit = probing_depth < max_probing_depth

    if needs_probing and within_limit:
        return "dynamic_probing"

    return "check_more_prompts"


def check_more_prompts(state: AgentState) -> Literal["primary_prompts", "check_extension"]:
    """Check if there are more primary prompts to deliver.

    Routes to primary_prompts if more remain, check_extension otherwise.
    """
    initial_prompts = state.get("initial_prompts", [])
    current_index = state.get("current_prompt_index", 0)

    if current_index < len(initial_prompts):
        return "primary_prompts"

    return "check_extension"


def check_completion(state: AgentState) -> Literal["extension", "closure", "continue"]:
    """Check if AI determined the assessment should complete.

    Routes based on completion_ready signal and extension policy.
    If completion_ready is True, goes to closure (skipping extension).
    If completion_ready is False and extension allowed, goes to extension.
    Otherwise goes to closure.
    """
    completion_ready = state.get("completion_ready", False)

    # If AI says we're done, go straight to closure
    if completion_ready:
        return "closure"

    # Otherwise check extension policy
    extension_policy = state.get("extension_policy", "disallowed")

    if extension_policy == "allowed":
        return "extension"

    if extension_policy == "conditional":
        # Check if all criteria were at least partially explored
        completion_analysis = state.get("completion_analysis")
        if completion_analysis:
            criteria_status = completion_analysis.get("criteria_status", {})
            all_touched = all(status != "NOT_TOUCHED" for status in criteria_status.values())
            if all_touched:
                return "extension"

    return "closure"


def check_extension(state: AgentState) -> Literal["extension", "closure"]:
    """Check if extension phase should be entered.

    Routes to extension if policy allows, closure otherwise.
    Note: For AI-driven completion, prefer using check_completion instead.
    """
    extension_policy = state.get("extension_policy", "disallowed")

    if extension_policy == "allowed":
        return "extension"

    if extension_policy == "conditional":
        # Could add logic to check if learner earned extension
        # For now, treat as allowed
        return "extension"

    return "closure"


def after_probing(state: AgentState) -> Literal["analyze_response", "check_more_prompts"]:
    """Route after probing based on whether we need to analyze the new response.

    After dynamic probing, we typically wait for the learner's response
    and then analyze it again.
    """
    # Check if there's a new learner message to analyze
    messages = state.get("messages", [])
    if messages and isinstance(messages[-1], HumanMessage):
        return "analyze_response"

    return "check_more_prompts"


def after_extension(state: AgentState) -> Literal["closure"]:
    """Route after extension phase.

    Always goes to closure after extension.
    """
    return "closure"


def route_by_phase(state: AgentState) -> str:
    """Route based on the current phase.

    This is a utility function for manual routing when needed.
    """
    phase = state.get("phase", InterviewPhase.Orientation)

    if phase == InterviewPhase.Orientation:
        return "orientation"
    elif phase == InterviewPhase.PrimaryPrompts:
        return "primary_prompts"
    elif phase == InterviewPhase.DynamicProbing:
        return "dynamic_probing"
    elif phase == InterviewPhase.Extension:
        return "extension"
    elif phase == InterviewPhase.Closure:
        return "closure"
    else:
        return "closure"


def is_interview_complete(state: AgentState) -> bool:
    """Check if the interview has reached completion.

    Used to determine when to finalize the assessment.
    """
    phase = state.get("phase")
    return phase == InterviewPhase.Complete


def should_continue_after_learner_response(
    state: AgentState,
) -> Literal["analyze_response", "closure"]:
    """Determine next action after receiving a learner response.

    This is the main entry point after each learner message.
    """
    phase = state.get("phase")

    if phase == InterviewPhase.Orientation:
        # Check consent and proceed
        consent_result = check_consent(state)
        if consent_result == "closure":
            return "closure"
        return "analyze_response"

    elif phase == InterviewPhase.PrimaryPrompts:
        return "analyze_response"

    elif phase == InterviewPhase.DynamicProbing:
        return "analyze_response"

    elif phase == InterviewPhase.Extension:
        # Extension can have multiple exchanges
        return "analyze_response"

    elif phase == InterviewPhase.Closure:
        # After closure, check if learner wants to correct anything
        return "closure"

    return "closure"
