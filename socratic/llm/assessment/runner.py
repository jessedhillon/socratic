"""Assessment runner for orchestrating interview turns."""

from __future__ import annotations

import typing as t

import jinja2
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from socratic.model import AttemptID

from .checkpointer import PostgresCheckpointer
from .graph import create_initial_state
from .nodes import analyze_completion_node, build_system_prompt, build_template_context, get_content_str, \
    render_template
from .state import AgentState, CoverageLevel, InterviewPhase

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

    # Analyze learner response for criteria coverage (after consent confirmed)
    if state.get("learner_consent_confirmed", False) and current_phase != InterviewPhase.Closure:
        analysis_result = await _analyze_response(state, learner_message, model, env)
        state.update(analysis_result)

    # Check if all prompts are complete BEFORE generating response
    if current_phase == InterviewPhase.PrimaryPrompts:
        current_index = state.get("current_prompt_index", 0)
        initial_prompts = state.get("initial_prompts", [])

        if current_index >= len(initial_prompts):
            # All prompts complete - run completion analysis now
            completion_result = await analyze_completion_node(state, model, env)
            state.update(completion_result)

            # Route based on completion analysis
            completion_ready = state.get("completion_ready", False)
            extension_policy = state.get("extension_policy", "disallowed")

            if completion_ready:
                state["phase"] = InterviewPhase.Closure
                current_phase = InterviewPhase.Closure
            elif extension_policy == "allowed":
                state["phase"] = InterviewPhase.Extension
                current_phase = InterviewPhase.Extension
            elif extension_policy == "conditional":
                completion_analysis = state.get("completion_analysis")
                if completion_analysis:
                    criteria_status = completion_analysis.get("criteria_status", {})
                    all_touched = all(status != "NOT_TOUCHED" for status in criteria_status.values())
                    if all_touched:
                        state["phase"] = InterviewPhase.Extension
                        current_phase = InterviewPhase.Extension
                    else:
                        state["phase"] = InterviewPhase.Closure
                        current_phase = InterviewPhase.Closure
                else:
                    state["phase"] = InterviewPhase.Closure
                    current_phase = InterviewPhase.Closure
            else:
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

    # Update prompt index after delivering a prompt (if still in PrimaryPrompts)
    if current_phase == InterviewPhase.PrimaryPrompts:
        current_index = state.get("current_prompt_index", 0)
        initial_prompts = state.get("initial_prompts", [])
        if current_index < len(initial_prompts):
            state["current_prompt_index"] = current_index + 1

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


async def _analyze_response(
    state: AgentState,
    learner_message: str,
    model: BaseChatModel,
    env: jinja2.Environment,
) -> dict[str, t.Any]:
    """Analyze the learner's response for criteria coverage.

    This is a simplified version of analyze_response_node that focuses
    on criteria coverage tracking without the full probing analysis.

    Args:
        state: Current assessment state
        learner_message: The learner's message text
        model: LLM for analysis
        env: Jinja2 environment for prompts

    Returns:
        Dict with updated criteria_coverage and current_turn
    """
    current_turn = state.get("current_turn", 0) + 1
    criteria_coverage = dict(state.get("criteria_coverage", {}))
    rubric_criteria = state.get("rubric_criteria", [])

    result: dict[str, t.Any] = {
        "current_turn": current_turn,
    }

    if not rubric_criteria:
        return result

    # Build system prompt for context
    system_prompt = build_system_prompt(env, state)

    # Build coverage analysis prompt
    coverage_prompt = render_template(
        env,
        "assessment/analyze_coverage.j2",
        learner_response=learner_message,
        rubric_criteria=rubric_criteria,
        criteria_coverage=criteria_coverage,
        conversation_history=[get_content_str(m.content) for m in state.get("messages", [])[-6:]],
    )

    # Get coverage analysis from LLM
    analysis_messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=coverage_prompt),
    ]

    response = await model.ainvoke(analysis_messages)
    response_text = get_content_str(response.content)

    # Parse coverage updates
    updated_coverage = _parse_coverage_response(
        response_text,
        criteria_coverage,
        current_turn,
    )
    result["criteria_coverage"] = updated_coverage

    return result


def _parse_coverage_response(
    response_text: str,
    current_coverage: dict[str, dict[str, t.Any]],
    current_turn: int,
) -> dict[str, dict[str, t.Any]]:
    """Parse the coverage analysis response and update coverage tracking.

    Expected format:
    - criterion_id: [none/partial/full] - "evidence quote"
    """
    import re as regex

    updated = dict(current_coverage)

    # Pattern to match coverage entries
    pattern = r"-\s*(\S+):\s*(none|partial|full)\s*-\s*\"([^\"]*)\""
    matches = regex.findall(pattern, response_text, regex.IGNORECASE)

    for criterion_id, level, evidence in matches:
        if criterion_id not in updated:
            continue

        entry = dict(updated[criterion_id])
        level_lower = level.lower()

        # Determine new coverage level
        if level_lower == "full":
            new_level = CoverageLevel.FullyExplored.value
        elif level_lower == "partial":
            new_level = CoverageLevel.PartiallyExplored.value
        else:
            new_level = entry.get("coverage_level", CoverageLevel.NotStarted.value)

        # Only upgrade coverage, never downgrade
        current_level = entry.get("coverage_level", CoverageLevel.NotStarted.value)
        if _coverage_level_rank(new_level) > _coverage_level_rank(current_level):
            entry["coverage_level"] = new_level

        # Add evidence if provided and not "no evidence"
        if evidence and evidence.lower() not in ("no evidence", "none", "n/a"):
            evidence_list = list(entry.get("evidence_found", []))
            if evidence not in evidence_list:
                evidence_list.append(evidence)
            entry["evidence_found"] = evidence_list
            entry["last_touched_turn"] = current_turn

        updated[criterion_id] = entry

    return updated


def _coverage_level_rank(level: str) -> int:
    """Get numeric rank for coverage level comparison."""
    ranks = {
        CoverageLevel.NotStarted.value: 0,
        CoverageLevel.PartiallyExplored.value: 1,
        CoverageLevel.FullyExplored.value: 2,
    }
    return ranks.get(level, 0)


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
