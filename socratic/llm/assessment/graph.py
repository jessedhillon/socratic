"""LangGraph construction for the assessment interview."""

from __future__ import annotations

import typing as t
from datetime import datetime, timezone
from functools import partial

import jinja2
from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, StateGraph

from .edges import after_extension, check_consent, check_extension, check_more_prompts, should_probe
from .nodes import analyze_response_node, closure_node, dynamic_probing_node, extension_node, orientation_node, \
    primary_prompts_node
from .state import AgentState, CoverageLevel

if t.TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph


def build_assessment_graph(
    model: BaseChatModel,
    env: jinja2.Environment,
) -> CompiledStateGraph:
    """Build and compile the assessment interview graph.

    Args:
        model: LangChain chat model for generating responses
        env: Jinja2 environment for loading prompt templates

    Returns:
        Compiled LangGraph ready for execution
    """
    # Create bound node functions with model and env
    bound_orientation = partial(orientation_node, model=model, env=env)
    bound_primary_prompts = partial(primary_prompts_node, model=model, env=env)
    bound_analyze_response = partial(analyze_response_node, model=model, env=env)
    bound_dynamic_probing = partial(dynamic_probing_node, model=model, env=env)
    bound_extension = partial(extension_node, model=model, env=env)
    bound_closure = partial(closure_node, model=model, env=env)

    # Create the graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("orientation", bound_orientation)
    graph.add_node("primary_prompts", bound_primary_prompts)
    graph.add_node("analyze_response", bound_analyze_response)
    graph.add_node("dynamic_probing", bound_dynamic_probing)
    graph.add_node("extension", bound_extension)
    graph.add_node("closure", bound_closure)

    # Set entry point
    graph.set_entry_point("orientation")

    # Add edges from orientation
    # After orientation, wait for learner response then check consent
    graph.add_conditional_edges(
        "orientation",
        check_consent,
        {
            "primary_prompts": "primary_prompts",
            "closure": "closure",
        },
    )

    # After primary prompts, analyze the response
    graph.add_edge("primary_prompts", "analyze_response")

    # After analysis, decide whether to probe or continue
    graph.add_conditional_edges(
        "analyze_response",
        should_probe,
        {
            "dynamic_probing": "dynamic_probing",
            "check_more_prompts": "check_more_prompts",
        },
    )

    # After probing, go back to analysis (wait for learner response)
    graph.add_edge("dynamic_probing", "analyze_response")

    # Check if more prompts remain
    graph.add_conditional_edges(
        "check_more_prompts",
        check_more_prompts,
        {
            "primary_prompts": "primary_prompts",
            "check_extension": "check_extension",
        },
    )

    # Check extension policy
    graph.add_conditional_edges(
        "check_extension",
        check_extension,
        {
            "extension": "extension",
            "closure": "closure",
        },
    )

    # After extension, go to closure
    graph.add_conditional_edges(
        "extension",
        after_extension,
        {
            "closure": "closure",
        },
    )

    # Closure ends the graph
    graph.add_edge("closure", END)

    return graph.compile()


def create_initial_state(
    attempt_id: str,
    objective_id: str,
    objective_title: str,
    objective_description: str,
    initial_prompts: list[str],
    rubric_criteria: list[dict[str, t.Any]],
    *,
    scope_boundaries: str | None = None,
    time_expectation_minutes: int | None = None,
    challenge_prompts: list[str] | None = None,
    extension_policy: str = "disallowed",
    max_probing_depth: int = 3,
) -> AgentState:
    """Create the initial state for a new assessment interview.

    Args:
        attempt_id: ID of the assessment attempt
        objective_id: ID of the learning objective
        objective_title: Title for display
        objective_description: Full description for context
        initial_prompts: Educator-defined questions
        rubric_criteria: Serialized rubric criteria
        scope_boundaries: What's NOT included
        time_expectation_minutes: Expected duration
        challenge_prompts: Additional probing questions
        extension_policy: "allowed", "disallowed", or "conditional"
        max_probing_depth: Maximum follow-up depth per prompt

    Returns:
        Initial AgentState ready for graph execution
    """
    # Initialize criteria coverage tracking
    criteria_coverage: dict[str, dict[str, t.Any]] = {}
    for criterion in rubric_criteria:
        criterion_id = criterion.get("criterion_id", "")
        criteria_coverage[criterion_id] = {
            "criterion_id": criterion_id,
            "criterion_name": criterion.get("name", ""),
            "coverage_level": CoverageLevel.NotStarted.value,
            "evidence_found": [],
            "last_touched_turn": 0,
        }

    return AgentState(
        messages=[],
        phase=None,  # Will be set by first node
        attempt_id=attempt_id,
        objective_id=objective_id,
        objective_title=objective_title,
        objective_description=objective_description,
        scope_boundaries=scope_boundaries,
        time_expectation_minutes=time_expectation_minutes,
        start_time=datetime.now(timezone.utc),  # Track assessment start time for pacing
        initial_prompts=initial_prompts,
        challenge_prompts=challenge_prompts or [],
        extension_policy=extension_policy,
        rubric_criteria=rubric_criteria,
        criteria_coverage=criteria_coverage,
        current_prompt_index=0,
        current_turn=0,
        probing_depth=0,
        max_probing_depth=max_probing_depth,
        learner_consent_confirmed=False,
        detected_ambiguity=False,
        detected_inconsistency=False,
        detected_evasion=False,
        ambiguous_phrase=None,
        earlier_point=None,
        current_point=None,
        probing_topic=None,
        key_points_summary=[],
    )
