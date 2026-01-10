"""Feedback generation for assessment results."""

from __future__ import annotations

import json
import re as regex
import typing as t

import jinja2
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from socratic.model import Grade

from .evidence import EvidenceResult
from .grader import CriterionGradeResult

if t.TYPE_CHECKING:
    from socratic.model import Objective


class FeedbackResult(t.TypedDict):
    """Generated feedback for the learner."""

    strengths: list[str]
    areas_for_growth: list[str]
    suggestions: list[str]
    summary: str


async def generate_feedback(
    evidence_results: list[EvidenceResult],
    criterion_grades: list[CriterionGradeResult],
    overall_grade: Grade,
    overall_confidence: float,
    objective: Objective,
    model: BaseChatModel,
    env: jinja2.Environment,
) -> FeedbackResult:
    """Generate learner-facing feedback based on evaluation results.

    Args:
        evidence_results: Evidence extracted for each criterion
        criterion_grades: Grades assigned to each criterion
        overall_grade: The overall grade assigned
        overall_confidence: Confidence in the overall grade
        objective: The learning objective
        model: LLM for feedback generation (should be feedback model)
        env: Jinja2 environment for prompts

    Returns:
        FeedbackResult with learner-facing feedback
    """
    # Build criterion results for template
    criterion_results = _build_criterion_results(evidence_results, criterion_grades)

    # Render the prompt
    template = env.get_template("evaluation/generate_feedback.j2")
    prompt = template.render(
        objective_title=objective.title,
        objective_description=objective.description,
        grade=overall_grade.value,
        confidence_score=overall_confidence,
        criterion_results=criterion_results,
    )

    # Build messages
    system_message = SystemMessage(
        content=(
            "You are a supportive educational feedback generator. Respond only with valid JSON, no markdown formatting."
        )
    )
    human_message = HumanMessage(content=prompt)

    # Get LLM response
    response = await model.ainvoke([system_message, human_message])
    response_text = _get_content_str(response.content)

    # Parse JSON response
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        parsed = _extract_json_from_response(response_text)

    return FeedbackResult(
        strengths=parsed.get("strengths", []),
        areas_for_growth=parsed.get("areas_for_growth", []),
        suggestions=parsed.get("suggestions", []),
        summary=parsed.get("summary", ""),
    )


def _build_criterion_results(
    evidence_results: list[EvidenceResult],
    criterion_grades: list[CriterionGradeResult],
) -> list[dict[str, t.Any]]:
    """Build combined criterion results for the template."""
    # Map criterion_id to grade result
    grades_by_id: dict[str, CriterionGradeResult] = {g["criterion_id"]: g for g in criterion_grades}

    results: list[dict[str, t.Any]] = []
    for evidence in evidence_results:
        criterion_id = evidence["criterion_id"]
        grade_result = grades_by_id.get(criterion_id)

        if grade_result is None:
            continue

        # Determine strengths and gaps from evidence
        strengths: list[str] = []
        gaps: list[str] = []

        if evidence["strength"] in ("strong", "moderate"):
            strengths = evidence["quotes"][:2]  # Top 2 quotes as strengths
        elif evidence["strength"] in ("weak", "none"):
            gaps.append(f"Limited evidence for {evidence['criterion_name']}")

        if evidence["failure_modes_detected"]:
            gaps.extend(f"Possible misconception: {fm}" for fm in evidence["failure_modes_detected"])

        results.append({
            "criterion_name": evidence["criterion_name"],
            "grade": grade_result["grade"],
            "evidence_strength": evidence["strength"],
            "strengths": strengths,
            "gaps": gaps,
        })

    return results


def _get_content_str(content: t.Any) -> str:
    """Extract string content from a LangChain message content field."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        content_list = t.cast(list[t.Any], content)
        parts: list[str] = []
        for item in content_list:
            if isinstance(item, str):
                parts.append(item)
        return " ".join(parts)
    return str(content)


def _extract_json_from_response(text: str) -> dict[str, t.Any]:
    """Try to extract JSON from a response that may contain markdown."""
    # Try to find JSON in code blocks
    json_match = regex.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, regex.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find raw JSON
    json_match = regex.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, regex.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return {
        "strengths": [],
        "areas_for_growth": [],
        "suggestions": [],
        "summary": "Unable to generate feedback at this time.",
    }
