"""Status message rendering for the assessment agent."""

from __future__ import annotations

import typing as t

import jinja2

from .state import AssessmentState, CoverageLevel


def render_status(state: AssessmentState, env: jinja2.Environment) -> str:
    """Render the assessment status message from current state.

    The status message is appended to the LLM input each turn, giving the
    model situational awareness about assessment progress.
    """
    template = env.get_template("agent/assessment_status.j2")
    context = _build_context(state)
    return template.render(**context)


def _build_context(state: AssessmentState) -> dict[str, t.Any]:
    """Build the template context from assessment state."""
    coverage_entries = sorted(
        state.criteria_coverage.values(),
        key=lambda c: (
            # Show least-covered criteria first
            0 if c.coverage == CoverageLevel.NotStarted else 1 if c.coverage == CoverageLevel.Partial else 2,
            c.criterion_name,
        ),
    )

    return {
        "criteria_coverage": [
            {
                "criterion_name": c.criterion_name,
                "coverage": c.coverage.value.replace("_", " "),
                "evidence": c.evidence,
            }
            for c in coverage_entries
        ],
        "available_prompts": state.initial_prompts,
        "turn_count": state.turn_count,
        "elapsed_minutes": (round(state.elapsed_minutes, 1) if state.elapsed_minutes is not None else None),
        "time_budget_minutes": state.time_budget_minutes,
    }
