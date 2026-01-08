"""Flag detection for assessment evaluation."""

from __future__ import annotations

import json
import typing as t

import jinja2
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from socratic.model import AssessmentFlag, TranscriptSegment, UtteranceType

from .evidence import EvidenceResult

if t.TYPE_CHECKING:
    from socratic.model import Objective

# Map flag type strings to AssessmentFlag enum
FLAG_TYPE_MAP: dict[str, AssessmentFlag] = {
    "HighFluencyLowSubstance": AssessmentFlag.HighFluencyLowSubstance,
    "RepeatedEvasion": AssessmentFlag.RepeatedEvasion,
    "VocabularyMirroring": AssessmentFlag.VocabularyMirroring,
    "InconsistentReasoning": AssessmentFlag.InconsistentReasoning,
    "PossibleGaming": AssessmentFlag.PossibleGaming,
}

# Confidence threshold for flagging
FLAG_CONFIDENCE_THRESHOLD = 0.7


class DetectedFlag(t.TypedDict):
    """A detected flag with evidence."""

    flag_type: str
    confidence: float
    evidence: str
    reasoning: str


class FlagResult(t.TypedDict):
    """Result of flag detection."""

    flags: list[AssessmentFlag]
    flag_details: list[DetectedFlag]
    overall_assessment: str


async def detect_flags(
    transcript: list[TranscriptSegment],
    evidence_results: list[EvidenceResult],
    objective: Objective,
    model: BaseChatModel,
    env: jinja2.Environment,
    *,
    overall_confidence: float = 1.0,
) -> FlagResult:
    """Detect assessment flags that may require educator review.

    Args:
        transcript: List of transcript segments
        evidence_results: Evidence extracted for each criterion
        objective: The learning objective
        model: LLM for flag detection
        env: Jinja2 environment for prompts
        overall_confidence: Overall grading confidence (for LowConfidence flag)

    Returns:
        FlagResult with detected flags and details
    """
    # Format transcript for template
    transcript_segments = [
        {
            "utterance_type": seg.utterance_type.value,
            "content": seg.content,
        }
        for seg in transcript
    ]

    # Format evidence mappings for template
    evidence_mappings = [
        {
            "criterion_name": e["criterion_name"],
            "strength": e["strength"],
            "failure_modes_detected": e["failure_modes_detected"],
        }
        for e in evidence_results
    ]

    # Get LLM-detected flags
    llm_flags = await _detect_llm_flags(
        transcript_segments=transcript_segments,
        evidence_mappings=evidence_mappings,
        objective=objective,
        model=model,
        env=env,
    )

    # Add heuristic-based flags
    heuristic_flags = _detect_heuristic_flags(
        transcript=transcript,
        evidence_results=evidence_results,
        overall_confidence=overall_confidence,
    )

    # Combine and deduplicate flags
    all_flag_details = llm_flags["flag_details"] + heuristic_flags
    seen_types: set[str] = set()
    unique_details: list[DetectedFlag] = []
    for detail in all_flag_details:
        if detail["flag_type"] not in seen_types:
            seen_types.add(detail["flag_type"])
            unique_details.append(detail)

    # Convert to AssessmentFlag enums
    flags: list[AssessmentFlag] = []
    for detail in unique_details:
        flag = FLAG_TYPE_MAP.get(detail["flag_type"])
        if flag is not None:
            flags.append(flag)

    return FlagResult(
        flags=flags,
        flag_details=unique_details,
        overall_assessment=llm_flags["overall_assessment"],
    )


async def _detect_llm_flags(
    transcript_segments: list[dict[str, str]],
    evidence_mappings: list[dict[str, t.Any]],
    objective: Objective,
    model: BaseChatModel,
    env: jinja2.Environment,
) -> dict[str, t.Any]:
    """Use LLM to detect flags."""
    # Render the prompt
    template = env.get_template("evaluation/detect_flags.j2")
    prompt = template.render(
        objective_title=objective.title,
        transcript_segments=transcript_segments,
        evidence_mappings=evidence_mappings,
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

    # Filter flags by confidence threshold
    flag_details: list[DetectedFlag] = []
    for flag_data in parsed.get("flags", []):
        if flag_data.get("confidence", 0) >= FLAG_CONFIDENCE_THRESHOLD:
            flag_details.append(
                DetectedFlag(
                    flag_type=flag_data.get("flag_type", ""),
                    confidence=flag_data.get("confidence", 0),
                    evidence=flag_data.get("evidence", ""),
                    reasoning=flag_data.get("reasoning", ""),
                )
            )

    return {
        "flag_details": flag_details,
        "overall_assessment": parsed.get("overall_assessment", ""),
    }


def _detect_heuristic_flags(
    transcript: list[TranscriptSegment],
    evidence_results: list[EvidenceResult],
    overall_confidence: float,
) -> list[DetectedFlag]:
    """Detect flags using heuristics (no LLM needed)."""
    flags: list[DetectedFlag] = []

    # LowConfidence flag
    if overall_confidence < 0.6:
        flags.append(
            DetectedFlag(
                flag_type="LowConfidence",
                confidence=1.0,
                evidence=f"Overall evaluation confidence: {overall_confidence:.2f}",
                reasoning="The evaluation system has low confidence in this assessment",
            )
        )

    # High fluency low substance heuristic
    # Count words in learner responses vs evidence extracted
    learner_word_count = sum(
        len(seg.content.split()) for seg in transcript if seg.utterance_type == UtteranceType.Learner
    )
    evidence_quote_count = sum(len(e["quotes"]) for e in evidence_results)

    if learner_word_count > 500 and evidence_quote_count < 3:
        flags.append(
            DetectedFlag(
                flag_type="HighFluencyLowSubstance",
                confidence=0.75,
                evidence=(
                    f"Learner spoke {learner_word_count} words "
                    f"but only {evidence_quote_count} evidence quotes extracted"
                ),
                reasoning="High word count relative to extracted evidence suggests fluency without substance",
            )
        )

    return flags


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

    # Try to find JSON in code blocks
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find raw JSON
    json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return {"flags": [], "overall_assessment": "Failed to parse LLM response"}
