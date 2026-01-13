"""Evidence extraction from assessment transcripts."""

from __future__ import annotations

import json
import re as regex
import typing as t

import jinja2
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from socratic.model import RubricCriterion, TranscriptSegment

if t.TYPE_CHECKING:
    from socratic.model import Objective


class EvidenceResult(t.TypedDict):
    """Result of evidence extraction for a single criterion."""

    criterion_id: str
    criterion_name: str
    evidence_present: bool
    quotes: list[str]
    strength: str  # "strong" | "moderate" | "weak" | "none"
    failure_modes_detected: list[str]
    reasoning: str


async def extract_evidence(
    transcript: list[TranscriptSegment],
    rubric_criteria: list[RubricCriterion],
    objective: Objective,
    model: BaseChatModel,
    env: jinja2.Environment,
) -> list[EvidenceResult]:
    """Extract evidence from transcript for each rubric criterion.

    Args:
        transcript: List of transcript segments from the assessment
        rubric_criteria: List of rubric criteria to evaluate against
        objective: The learning objective being assessed
        model: LLM for analysis (should be evaluation model with low temperature)
        env: Jinja2 environment for prompts

    Returns:
        List of EvidenceResult, one per criterion
    """
    results: list[EvidenceResult] = []

    # Format transcript for template
    transcript_segments = [
        {
            "utterance_type": seg.utterance_type.value,
            "content": seg.content,
        }
        for seg in transcript
    ]

    for criterion in rubric_criteria:
        result = await _extract_criterion_evidence(
            transcript_segments=transcript_segments,
            criterion=criterion,
            objective=objective,
            model=model,
            env=env,
        )
        results.append(result)

    return results


async def _extract_criterion_evidence(
    transcript_segments: list[dict[str, str]],
    criterion: RubricCriterion,
    objective: Objective,
    model: BaseChatModel,
    env: jinja2.Environment,
) -> EvidenceResult:
    """Extract evidence for a single criterion."""
    # Build criterion context for template
    criterion_context = {
        "name": criterion.name,
        "description": criterion.description,
        "proficiency_levels": [
            {
                "grade": pl.grade,
                "description": pl.description,
            }
            for pl in criterion.proficiency_levels
        ],
    }

    # Render the prompt
    template = env.get_template("evaluation/extract_evidence.j2")
    prompt = template.render(
        objective_title=objective.title,
        objective_description=objective.description,
        criterion=criterion_context,
        transcript_segments=transcript_segments,
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
        # Try to extract JSON from response if it contains markdown
        parsed = _extract_json_from_response(response_text)

    return EvidenceResult(
        criterion_id=str(criterion.criterion_id),
        criterion_name=criterion.name,
        evidence_present=parsed.get("evidence_present", False),
        quotes=parsed.get("quotes", []),
        strength=parsed.get("strength", "none"),
        failure_modes_detected=parsed.get("failure_modes_detected", []),
        reasoning=parsed.get("reasoning", ""),
    )


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
    json_match = regex.search(r"\{[^{}]*\}", text, regex.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    # Return default structure
    return {
        "evidence_present": False,
        "quotes": [],
        "strength": "none",
        "failure_modes_detected": [],
        "reasoning": "Failed to parse LLM response",
    }
