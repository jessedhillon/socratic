"""Node implementations for each interview phase."""

from __future__ import annotations

import re as regex
import typing as t

import jinja2
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from .state import AgentState, calculate_pacing_status, CompletionAnalysis, CoverageLevel, InterviewPhase

if t.TYPE_CHECKING:
    from collections.abc import AsyncIterator


def get_content_str(content: t.Any) -> str:
    """Extract string content from a LangChain message content field.

    LangChain's content type is `str | list[str | dict]`, but we always
    want a string for our use cases.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Multimodal content - extract text parts
        content_list = t.cast(list[t.Any], content)
        parts: list[str] = []
        for item in content_list:
            if isinstance(item, str):
                parts.append(item)
        return " ".join(parts)
    return str(content)


def render_template(
    env: jinja2.Environment,
    template_name: str,
    **context: t.Any,
) -> str:
    """Render a Jinja2 template with the given context."""
    template = env.get_template(template_name)
    return template.render(**context)


def build_system_prompt(env: jinja2.Environment, state: AgentState) -> str:
    """Build the system prompt with objective and rubric context."""
    return render_template(
        env,
        "assessment/system.j2",
        objective_title=state.get("objective_title", ""),
        objective_description=state.get("objective_description", ""),
        scope_boundaries=state.get("scope_boundaries"),
        rubric_criteria=state.get("rubric_criteria", []),
    )


async def orientation_node(
    state: AgentState,
    model: BaseChatModel,
    env: jinja2.Environment,
) -> dict[str, t.Any]:
    """Generate orientation message explaining format and requesting consent.

    This is the entry point for the interview. The AI explains the process
    and asks the learner if they're ready to begin.
    """
    system_prompt = build_system_prompt(env, state)
    orientation_prompt = render_template(
        env,
        "assessment/orientation.j2",
        objective_title=state.get("objective_title", ""),
        time_expectation_minutes=state.get("time_expectation_minutes", 15),
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=orientation_prompt),
    ]

    response = await model.ainvoke(messages)
    ai_message = AIMessage(content=get_content_str(response.content))

    return {
        "messages": [ai_message],
        "phase": InterviewPhase.Orientation,
    }


async def primary_prompts_node(
    state: AgentState,
    model: BaseChatModel,
    env: jinja2.Environment,
) -> dict[str, t.Any]:
    """Deliver the next educator-defined prompt.

    Progresses through initial_prompts sequentially.
    """
    initial_prompts = state.get("initial_prompts", [])
    current_index = state.get("current_prompt_index", 0)

    if current_index >= len(initial_prompts):
        # No more prompts, should transition to extension/closure
        return {"phase": InterviewPhase.PrimaryPrompts}

    current_prompt = initial_prompts[current_index]

    system_prompt = build_system_prompt(env, state)
    prompt_instruction = render_template(
        env,
        "assessment/primary_prompt.j2",
        current_prompt=current_prompt,
        prompt_number=current_index + 1,
        total_prompts=len(initial_prompts),
        rubric_criteria=state.get("rubric_criteria", []),
    )

    # Build conversation history
    history = state.get("messages", [])
    messages = [SystemMessage(content=system_prompt)] + list(history) + [HumanMessage(content=prompt_instruction)]

    response = await model.ainvoke(messages)
    ai_message = AIMessage(content=get_content_str(response.content))

    return {
        "messages": history + [ai_message],
        "phase": InterviewPhase.PrimaryPrompts,
        "current_prompt_index": current_index + 1,
        "probing_depth": 0,  # Reset probing depth for new prompt
    }


async def analyze_response_node(
    state: AgentState,
    model: BaseChatModel,
    env: jinja2.Environment,
) -> dict[str, t.Any]:
    """Analyze the learner's response for quality signals and criteria coverage.

    This node runs internally without generating a visible message.
    It sets flags for ambiguity, inconsistency, or evasion, and updates
    criteria coverage tracking.
    """
    messages = state.get("messages", [])
    if not messages:
        return {}

    # Get the last learner message
    learner_messages = [m for m in messages if isinstance(m, HumanMessage)]
    if not learner_messages:
        return {}

    last_learner_message = learner_messages[-1]
    current_turn = state.get("current_turn", 0) + 1

    system_prompt = build_system_prompt(env, state)

    # First analysis: quality signals (ambiguity, inconsistency, evasion)
    quality_prompt = render_template(
        env,
        "assessment/analyze_response.j2",
        learner_response=last_learner_message.content,
        rubric_criteria=state.get("rubric_criteria", []),
        conversation_history=[m.content for m in messages[-6:]],
    )

    quality_messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=quality_prompt),
    ]

    quality_response = await model.ainvoke(quality_messages)
    quality_text = get_content_str(quality_response.content).lower()

    # Parse quality flags
    detected_ambiguity = "ambiguous" in quality_text or "unclear" in quality_text
    detected_inconsistency = "inconsistent" in quality_text or "contradicts" in quality_text
    detected_evasion = "evasion" in quality_text or "avoids" in quality_text

    result: dict[str, t.Any] = {
        "detected_ambiguity": detected_ambiguity,
        "detected_inconsistency": detected_inconsistency,
        "detected_evasion": detected_evasion,
        "current_turn": current_turn,
    }

    # Extract context for probing if needed
    if detected_ambiguity:
        result["ambiguous_phrase"] = _extract_quote(quality_text, "ambiguous")
    if detected_inconsistency:
        result["earlier_point"] = _extract_quote(quality_text, "earlier")
        result["current_point"] = _extract_quote(quality_text, "now")

    # Second analysis: criteria coverage
    criteria_coverage = dict(state.get("criteria_coverage", {}))
    rubric_criteria = state.get("rubric_criteria", [])

    if rubric_criteria:
        coverage_prompt = render_template(
            env,
            "assessment/analyze_coverage.j2",
            learner_response=last_learner_message.content,
            rubric_criteria=rubric_criteria,
            criteria_coverage=criteria_coverage,
            conversation_history=[m.content for m in messages[-6:]],
        )

        coverage_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=coverage_prompt),
        ]

        coverage_response = await model.ainvoke(coverage_messages)
        coverage_text = get_content_str(coverage_response.content)

        # Parse coverage updates
        updated_coverage = _parse_coverage_response(
            coverage_text,
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


def _extract_quote(text: str, keyword: str) -> str | None:
    """Extract a quoted phrase near a keyword from analysis text."""
    # Simple heuristic - look for quoted text near keyword
    pattern = rf'{keyword}[^"]*"([^"]+)"'
    match = regex.search(pattern, text, regex.IGNORECASE)
    return match.group(1) if match else None


async def analyze_completion_node(
    state: AgentState,
    model: BaseChatModel,
    env: jinja2.Environment,
) -> dict[str, t.Any]:
    """Analyze whether the assessment should conclude.

    Uses AI with structured output to determine if all criteria have been
    sufficiently explored and whether further probing would yield meaningful
    information.
    """
    messages = state.get("messages", [])
    initial_prompts = state.get("initial_prompts", [])
    current_index = state.get("current_prompt_index", 0)

    # Only run completion analysis if we've covered all prompts
    if current_index < len(initial_prompts):
        return {"completion_ready": False}

    system_prompt = build_system_prompt(env, state)
    completion_prompt = render_template(
        env,
        "assessment/analyze_completion.j2",
        objective_title=state.get("objective_title", ""),
        rubric_criteria=state.get("rubric_criteria", []),
        conversation_summary=summarize_conversation(messages),
        prompts_completed=current_index,
        total_prompts=len(initial_prompts),
        probing_depth=state.get("probing_depth", 0),
    )

    completion_messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=completion_prompt),
    ]

    # Use structured output for reliable schema-validated response
    # LangChain's with_structured_output has incomplete types, so we cast the result
    structured_model = model.with_structured_output(CompletionAnalysis)  # pyright: ignore[reportUnknownVariableType]
    result = await structured_model.ainvoke(completion_messages)  # pyright: ignore[reportUnknownVariableType]
    analysis = t.cast(CompletionAnalysis, result)

    # Ensure all criteria are represented (default to NOT_TOUCHED if missing)
    rubric_criteria = state.get("rubric_criteria", [])
    for criterion in rubric_criteria:
        name = criterion.get("name", "")
        if name and name not in analysis.criteria_status:
            analysis.criteria_status[name] = "NOT_TOUCHED"

    return {
        "completion_analysis": analysis.model_dump(),
        "completion_ready": analysis.completion_ready,
    }


async def dynamic_probing_node(
    state: AgentState,
    model: BaseChatModel,
    env: jinja2.Environment,
) -> dict[str, t.Any]:
    """Generate a follow-up question to clarify or challenge.

    Uses challenge_prompts or generates custom probes based on detected issues.
    """
    system_prompt = build_system_prompt(env, state)
    probing_prompt = render_template(
        env,
        "assessment/probing.j2",
        detected_ambiguity=state.get("detected_ambiguity", False),
        detected_inconsistency=state.get("detected_inconsistency", False),
        detected_evasion=state.get("detected_evasion", False),
        ambiguous_phrase=state.get("ambiguous_phrase"),
        earlier_point=state.get("earlier_point"),
        current_point=state.get("current_point"),
        probing_topic=state.get("probing_topic"),
        challenge_prompts=state.get("challenge_prompts", []),
        probing_depth=state.get("probing_depth", 0),
    )

    history = state.get("messages", [])
    messages = [SystemMessage(content=system_prompt)] + list(history) + [HumanMessage(content=probing_prompt)]

    response = await model.ainvoke(messages)
    ai_message = AIMessage(content=get_content_str(response.content))

    return {
        "messages": history + [ai_message],
        "phase": InterviewPhase.DynamicProbing,
        "probing_depth": state.get("probing_depth", 0) + 1,
        # Reset flags after probing
        "detected_ambiguity": False,
        "detected_inconsistency": False,
        "detected_evasion": False,
    }


async def extension_node(
    state: AgentState,
    model: BaseChatModel,
    env: jinja2.Environment,
) -> dict[str, t.Any]:
    """Facilitate exploratory discussion beyond required prompts.

    This phase is optional and allows learners to demonstrate deeper understanding.
    """
    system_prompt = build_system_prompt(env, state)
    extension_prompt = render_template(
        env,
        "assessment/extension.j2",
        objective_title=state.get("objective_title", ""),
        key_topics_covered=[],  # Could be extracted from conversation
    )

    history = state.get("messages", [])
    messages = [SystemMessage(content=system_prompt)] + list(history) + [HumanMessage(content=extension_prompt)]

    response = await model.ainvoke(messages)
    ai_message = AIMessage(content=get_content_str(response.content))

    return {
        "messages": history + [ai_message],
        "phase": InterviewPhase.Extension,
    }


async def closure_node(
    state: AgentState,
    model: BaseChatModel,
    env: jinja2.Environment,
) -> dict[str, t.Any]:
    """Summarize the discussion and allow learner correction.

    Critical guardrail against AI misinterpretation per PRODUCT.md.
    """
    system_prompt = build_system_prompt(env, state)
    closure_prompt = render_template(
        env,
        "assessment/closure.j2",
        objective_title=state.get("objective_title", ""),
        conversation_summary=summarize_conversation(state.get("messages", [])),
    )

    history = state.get("messages", [])
    messages = [SystemMessage(content=system_prompt)] + list(history) + [HumanMessage(content=closure_prompt)]

    response = await model.ainvoke(messages)
    ai_message = AIMessage(content=get_content_str(response.content))

    return {
        "messages": history + [ai_message],
        "phase": InterviewPhase.Closure,
    }


def summarize_conversation(messages: list[t.Any]) -> str:
    """Generate a brief summary of the conversation for closure."""
    learner_points: list[str] = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            content = get_content_str(msg.content)
            if len(content) > 20:
                # Extract first sentence or first 100 chars
                first_sentence = content.split(".")[0]
                if len(first_sentence) < 150:
                    learner_points.append(first_sentence)
    return "; ".join(learner_points[:5]) if learner_points else "the topics we discussed"


async def stream_node_response(
    state: AgentState,
    model: BaseChatModel,
    env: jinja2.Environment,
    phase: InterviewPhase,
) -> AsyncIterator[str]:
    """Stream the response for a given phase.

    Used by the runner to provide SSE streaming to the client.
    """
    system_prompt = build_system_prompt(env, state)
    history = state.get("messages", [])

    # Select template based on phase
    template_map = {
        InterviewPhase.Orientation: "assessment/orientation.j2",
        InterviewPhase.PrimaryPrompts: "assessment/primary_prompt.j2",
        InterviewPhase.DynamicProbing: "assessment/probing.j2",
        InterviewPhase.Extension: "assessment/extension.j2",
        InterviewPhase.Closure: "assessment/closure.j2",
    }

    template_name = template_map.get(phase, "assessment/primary_prompt.j2")

    # Build context based on phase
    context = build_template_context(state, phase)
    prompt = render_template(env, template_name, **context)

    messages = [SystemMessage(content=system_prompt)] + list(history) + [HumanMessage(content=prompt)]

    async for chunk in model.astream(messages):
        if hasattr(chunk, "content") and chunk.content:
            yield get_content_str(chunk.content)


def build_template_context(state: AgentState, phase: InterviewPhase) -> dict[str, t.Any]:
    """Build template context based on current phase."""
    base_context: dict[str, t.Any] = {
        "objective_title": state.get("objective_title", ""),
        "objective_description": state.get("objective_description", ""),
        "rubric_criteria": state.get("rubric_criteria", []),
        "criteria_coverage": state.get("criteria_coverage", {}),
    }

    # Add pacing info for all phases after orientation
    if phase != InterviewPhase.Orientation:
        pacing = calculate_pacing_status(
            state.get("start_time"),
            state.get("time_expectation_minutes"),
        )
        base_context["pacing"] = pacing

    if phase == InterviewPhase.Orientation:
        base_context["time_expectation_minutes"] = state.get("time_expectation_minutes", 15)

    elif phase == InterviewPhase.PrimaryPrompts:
        initial_prompts = state.get("initial_prompts", [])
        current_index = state.get("current_prompt_index", 0)
        if current_index < len(initial_prompts):
            base_context["current_prompt"] = initial_prompts[current_index]
            base_context["prompt_number"] = current_index + 1
            base_context["total_prompts"] = len(initial_prompts)

    elif phase == InterviewPhase.DynamicProbing:
        base_context.update({
            "detected_ambiguity": state.get("detected_ambiguity", False),
            "detected_inconsistency": state.get("detected_inconsistency", False),
            "detected_evasion": state.get("detected_evasion", False),
            "ambiguous_phrase": state.get("ambiguous_phrase"),
            "earlier_point": state.get("earlier_point"),
            "current_point": state.get("current_point"),
            "challenge_prompts": state.get("challenge_prompts", []),
            "probing_depth": state.get("probing_depth", 0),
        })

    elif phase == InterviewPhase.Closure:
        base_context["conversation_summary"] = summarize_conversation(state.get("messages", []))

    return base_context
