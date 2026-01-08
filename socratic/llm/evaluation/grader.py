"""Grading logic for assessment evaluation."""

from __future__ import annotations

import json
import typing as t

import jinja2
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from socratic.model import Grade, RubricCriterion

from .evidence import EvidenceResult

# Grade to numeric mapping for calculations
GRADE_VALUES: dict[str, int] = {
    "S": 3,
    "A": 2,
    "C": 1,
    "F": 0,
}

# Thresholds for overall grade
GRADE_THRESHOLDS: list[tuple[float, Grade]] = [
    (2.5, Grade.S),
    (1.5, Grade.A),
    (0.5, Grade.C),
    (0.0, Grade.F),
]


class CriterionGradeResult(t.TypedDict):
    """Grade result for a single criterion."""

    criterion_id: str
    criterion_name: str
    grade: str
    confidence: float
    reasoning: str


class GradingResult(t.TypedDict):
    """Overall grading result."""

    criterion_grades: list[CriterionGradeResult]
    overall_grade: str
    overall_confidence: float
    reasoning: str


async def grade_criteria(
    evidence_results: list[EvidenceResult],
    rubric_criteria: list[RubricCriterion],
    model: BaseChatModel,
    env: jinja2.Environment,
) -> GradingResult:
    """Grade each criterion and compute overall grade.

    Args:
        evidence_results: Evidence extracted for each criterion
        rubric_criteria: The rubric criteria with grade thresholds
        model: LLM for grading decisions
        env: Jinja2 environment for prompts

    Returns:
        GradingResult with per-criterion and overall grades
    """
    # Create a mapping of criterion_id to criterion
    criteria_by_id = {str(c.criterion_id): c for c in rubric_criteria}

    # Grade each criterion
    criterion_grades: list[CriterionGradeResult] = []
    for evidence in evidence_results:
        criterion = criteria_by_id.get(evidence["criterion_id"])
        if criterion is None:
            continue

        grade_result = await _grade_single_criterion(
            evidence=evidence,
            criterion=criterion,
            model=model,
            env=env,
        )
        criterion_grades.append(grade_result)

    # Compute overall grade
    overall_grade, overall_confidence = _compute_overall_grade(criterion_grades, rubric_criteria)

    return GradingResult(
        criterion_grades=criterion_grades,
        overall_grade=overall_grade.value,
        overall_confidence=overall_confidence,
        reasoning=_build_overall_reasoning(criterion_grades),
    )


async def _grade_single_criterion(
    evidence: EvidenceResult,
    criterion: RubricCriterion,
    model: BaseChatModel,
    env: jinja2.Environment,
) -> CriterionGradeResult:
    """Grade a single criterion using LLM."""
    # Build criterion context
    criterion_context = {
        "name": criterion.name,
        "description": criterion.description,
        "grade_thresholds": [
            {
                "grade": gt.grade,
                "description": gt.description,
                "min_evidence_count": gt.min_evidence_count,
            }
            for gt in criterion.grade_thresholds
        ],
    }

    # Render the prompt
    template = env.get_template("evaluation/grade_criteria.j2")
    prompt = template.render(
        criterion=criterion_context,
        evidence=evidence,
    )

    # Build messages
    system_message = SystemMessage(
        content="You are an expert evaluator. Respond only with valid JSON, no markdown formatting."
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

    return CriterionGradeResult(
        criterion_id=evidence["criterion_id"],
        criterion_name=evidence["criterion_name"],
        grade=parsed.get("grade", "F"),
        confidence=parsed.get("confidence", 0.5),
        reasoning=parsed.get("reasoning", ""),
    )


def _compute_overall_grade(
    criterion_grades: list[CriterionGradeResult],
    rubric_criteria: list[RubricCriterion],
) -> tuple[Grade, float]:
    """Compute overall grade from weighted criterion grades."""
    if not criterion_grades:
        return Grade.F, 0.0

    # Create weight mapping
    weights_by_id = {str(c.criterion_id): float(c.weight) for c in rubric_criteria}

    total_weight = 0.0
    weighted_sum = 0.0
    min_confidence = 1.0

    for grade_result in criterion_grades:
        weight = weights_by_id.get(grade_result["criterion_id"], 1.0)
        grade_value = GRADE_VALUES.get(grade_result["grade"], 0)

        weighted_sum += grade_value * weight
        total_weight += weight
        min_confidence = min(min_confidence, grade_result["confidence"])

    if total_weight == 0:
        return Grade.F, 0.0

    weighted_average = weighted_sum / total_weight

    # Map to grade
    overall_grade = Grade.F
    for threshold, grade in GRADE_THRESHOLDS:
        if weighted_average >= threshold:
            overall_grade = grade
            break

    # Confidence is the minimum of all criterion confidences
    # adjusted by evidence coverage
    evidence_coverage = len(criterion_grades) / max(len(rubric_criteria), 1)
    overall_confidence = min_confidence * evidence_coverage

    return overall_grade, overall_confidence


def _build_overall_reasoning(criterion_grades: list[CriterionGradeResult]) -> str:
    """Build a summary reasoning from criterion grades."""
    summaries: list[str] = []
    for grade_result in criterion_grades:
        summaries.append(f"{grade_result['criterion_name']}: {grade_result['grade']} - {grade_result['reasoning']}")
    return "; ".join(summaries)


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
    import re

    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return {"grade": "F", "confidence": 0.0, "reasoning": "Failed to parse LLM response"}
