"""Assessment runner for orchestrating interview turns."""

from __future__ import annotations

import typing as t

import jinja2
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from socratic.model import AttemptID

from .checkpointer import PostgresCheckpointer
from .graph import create_initial_state
from .nodes import build_system_prompt, build_template_context, get_content_str, render_template
from .state import InterviewPhase

if t.TYPE_CHECKING:
    from collections.abc import AsyncIterator


async def run_assessment_turn(
    attempt_id: AttemptID,
    learner_message: str,
    checkpointer: PostgresCheckpointer,
    model: BaseChatModel,
    env: jinja2.Environment,
) -> AsyncIterator[str]:
    """Run a single turn of the assessment conversation.

    Loads state, processes the learner's message, generates a response,
    and saves the updated state.

    Args:
        attempt_id: The assessment attempt ID
        learner_message: The learner's message text
        checkpointer: Checkpointer for state persistence
        model: LLM for generating responses
        env: Jinja2 environment for prompts

    Yields:
        Streamed response tokens from the AI
    """
    # Load current state
    state = checkpointer.get(attempt_id)
    if state is None:
        yield "Error: Assessment session not found."
        return

    # Add learner message to history
    messages = list(state.get("messages", []))
    messages.append(HumanMessage(content=learner_message))
    state["messages"] = messages

    # Determine next phase based on current state
    current_phase = state.get("phase", InterviewPhase.Orientation)

    # Handle consent check if in orientation
    if current_phase == InterviewPhase.Orientation:
        if _check_consent(learner_message):
            state["learner_consent_confirmed"] = True
            state["phase"] = InterviewPhase.PrimaryPrompts
            current_phase = InterviewPhase.PrimaryPrompts
        else:
            # Check if they're declining
            if _check_decline(learner_message):
                state["phase"] = InterviewPhase.Closure
                current_phase = InterviewPhase.Closure

    # Build prompts and generate response
    system_prompt = build_system_prompt(env, state)
    context = build_template_context(state, current_phase)

    template_map = {
        InterviewPhase.Orientation: "assessment/orientation.j2",
        InterviewPhase.PrimaryPrompts: "assessment/primary_prompt.j2",
        InterviewPhase.DynamicProbing: "assessment/probing.j2",
        InterviewPhase.Extension: "assessment/extension.j2",
        InterviewPhase.Closure: "assessment/closure.j2",
    }

    template_name = template_map.get(current_phase, "assessment/primary_prompt.j2")
    instruction = render_template(env, template_name, **context)

    # Build the full message list for the LLM
    llm_messages = [
        SystemMessage(content=system_prompt),
        *messages,
        HumanMessage(content=instruction),
    ]

    # Stream the response
    full_response = ""
    async for chunk in model.astream(llm_messages):
        if hasattr(chunk, "content") and chunk.content:
            token = get_content_str(chunk.content)
            full_response += token
            yield token

    # Add AI response to messages
    messages.append(AIMessage(content=full_response))
    state["messages"] = messages

    # Update phase tracking
    if current_phase == InterviewPhase.PrimaryPrompts:
        # Increment prompt index after delivering a prompt
        current_index = state.get("current_prompt_index", 0)
        initial_prompts = state.get("initial_prompts", [])
        if current_index < len(initial_prompts):
            state["current_prompt_index"] = current_index + 1
        else:
            # Move to extension or closure
            if state.get("extension_policy") == "allowed":
                state["phase"] = InterviewPhase.Extension
            else:
                state["phase"] = InterviewPhase.Closure

    # Save updated state
    checkpointer.put(attempt_id, state)


async def start_assessment(
    attempt_id: AttemptID,
    objective_id: str,
    objective_title: str,
    objective_description: str,
    initial_prompts: list[str],
    rubric_criteria: list[dict[str, t.Any]],
    checkpointer: PostgresCheckpointer,
    model: BaseChatModel,
    env: jinja2.Environment,
    *,
    scope_boundaries: str | None = None,
    time_expectation_minutes: int | None = None,
    challenge_prompts: list[str] | None = None,
    extension_policy: str = "disallowed",
) -> AsyncIterator[str]:
    """Start a new assessment and generate the orientation message.

    Args:
        attempt_id: The assessment attempt ID
        objective_id: Learning objective ID
        objective_title: Title for display
        objective_description: Full description
        initial_prompts: Educator-defined questions
        rubric_criteria: Serialized rubric criteria
        checkpointer: Checkpointer for state persistence
        model: LLM for generating responses
        env: Jinja2 environment for prompts
        scope_boundaries: What's not included
        time_expectation_minutes: Expected duration
        challenge_prompts: Additional probing questions
        extension_policy: "allowed", "disallowed", or "conditional"

    Yields:
        Streamed orientation message tokens
    """
    # Create initial state
    state = create_initial_state(
        attempt_id=str(attempt_id),
        objective_id=objective_id,
        objective_title=objective_title,
        objective_description=objective_description,
        initial_prompts=initial_prompts,
        rubric_criteria=rubric_criteria,
        scope_boundaries=scope_boundaries,
        time_expectation_minutes=time_expectation_minutes,
        challenge_prompts=challenge_prompts,
        extension_policy=extension_policy,
    )

    # Build orientation message
    system_prompt = build_system_prompt(env, state)
    orientation_prompt = render_template(
        env,
        "assessment/orientation.j2",
        objective_title=objective_title,
        time_expectation_minutes=time_expectation_minutes or 15,
    )

    llm_messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=orientation_prompt),
    ]

    # Stream the orientation
    full_response = ""
    async for chunk in model.astream(llm_messages):
        if hasattr(chunk, "content") and chunk.content:
            token = get_content_str(chunk.content)
            full_response += token
            yield token

    # Save initial state with orientation message
    state["messages"] = [AIMessage(content=full_response)]
    state["phase"] = InterviewPhase.Orientation
    checkpointer.put(AttemptID(str(attempt_id)), state)


def _check_consent(message: str) -> bool:
    """Check if the learner's message indicates consent."""
    message_lower = message.lower()
    consent_keywords = ["yes", "ready", "let's go", "begin", "start", "okay", "ok", "sure", "yep", "yeah"]
    return any(keyword in message_lower for keyword in consent_keywords)


def _check_decline(message: str) -> bool:
    """Check if the learner's message indicates declining."""
    message_lower = message.lower()
    decline_keywords = ["no", "not ready", "stop", "cancel", "quit", "don't", "cant", "can't"]
    return any(keyword in message_lower for keyword in decline_keywords)


def get_assessment_status(
    attempt_id: AttemptID,
    checkpointer: PostgresCheckpointer,
) -> dict[str, t.Any]:
    """Get the current status of an assessment.

    Returns:
        Dict with phase, message_count, and progress info
    """
    state = checkpointer.get(attempt_id)
    if state is None:
        return {"error": "Assessment not found"}

    messages = state.get("messages", [])
    phase = state.get("phase", InterviewPhase.Orientation)
    initial_prompts = state.get("initial_prompts", [])
    current_index = state.get("current_prompt_index", 0)

    return {
        "phase": phase.value if isinstance(phase, InterviewPhase) else str(phase),
        "message_count": len(messages),
        "prompts_completed": current_index,
        "total_prompts": len(initial_prompts),
        "consent_confirmed": state.get("learner_consent_confirmed", False),
    }
