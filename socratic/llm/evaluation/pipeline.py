"""Evaluation pipeline orchestrator."""

from __future__ import annotations

import decimal
import typing as t

import jinja2

from socratic.llm.factory import ModelFactory
from socratic.model import AssessmentFlag, AttemptID, EvidenceMapping, Grade, Objective, RubricCriterion, \
    RubricCriterionID, TranscriptSegment

from .evidence import EvidenceResult as ExtractedEvidence
from .evidence import extract_evidence
from .feedback import FeedbackResult, generate_feedback
from .flagger import detect_flags
from .grader import grade_criteria, GradingResult


class EvaluationOutput(t.TypedDict):
    """Complete output from the evaluation pipeline."""

    grade: Grade
    confidence_score: decimal.Decimal
    evidence_mappings: list[EvidenceMapping]
    flags: list[AssessmentFlag]
    strengths: list[str]
    gaps: list[str]
    reasoning_summary: str
    feedback: FeedbackResult


class EvaluationPipeline:
    """Orchestrates the full evaluation of an assessment attempt.

    The pipeline:
    1. Extracts evidence from transcript for each rubric criterion
    2. Grades each criterion based on extracted evidence
    3. Computes overall grade with confidence score
    4. Detects assessment flags (gaming, evasion, etc.)
    5. Generates learner-facing feedback
    """

    def __init__(
        self,
        model_factory: ModelFactory,
        env: jinja2.Environment,
    ) -> None:
        """Initialize the pipeline.

        Args:
            model_factory: Factory for creating LLM instances
            env: Jinja2 environment for prompt templates
        """
        self._model_factory = model_factory
        self._env = env

    async def evaluate(
        self,
        attempt_id: AttemptID,
        transcript: list[TranscriptSegment],
        rubric_criteria: list[RubricCriterion],
        objective: Objective,
    ) -> EvaluationOutput:
        """Run the full evaluation pipeline.

        Args:
            attempt_id: The assessment attempt being evaluated
            transcript: List of transcript segments from the assessment
            rubric_criteria: Rubric criteria for the objective
            objective: The learning objective being assessed

        Returns:
            EvaluationOutput with all evaluation results
        """
        # Get the appropriate models
        eval_model = self._model_factory.create_evaluation_model()
        feedback_model = self._model_factory.create_feedback_model()

        # Step 1: Extract evidence for each criterion
        evidence_results = await extract_evidence(
            transcript=transcript,
            rubric_criteria=rubric_criteria,
            objective=objective,
            model=eval_model,
            env=self._env,
        )

        # Step 2: Grade each criterion
        grading_result = await grade_criteria(
            evidence_results=evidence_results,
            rubric_criteria=rubric_criteria,
            model=eval_model,
            env=self._env,
        )

        # Step 3: Detect flags
        flag_result = await detect_flags(
            transcript=transcript,
            evidence_results=evidence_results,
            objective=objective,
            model=eval_model,
            env=self._env,
            overall_confidence=grading_result["overall_confidence"],
        )

        # Step 4: Generate feedback
        overall_grade = Grade(grading_result["overall_grade"])
        feedback_result = await generate_feedback(
            evidence_results=evidence_results,
            criterion_grades=grading_result["criterion_grades"],
            overall_grade=overall_grade,
            overall_confidence=grading_result["overall_confidence"],
            objective=objective,
            model=feedback_model,
            env=self._env,
        )

        # Build evidence mappings for storage
        evidence_mappings = _build_evidence_mappings(evidence_results, transcript)

        # Build strengths and gaps lists
        strengths, gaps = _extract_strengths_and_gaps(evidence_results, grading_result, feedback_result)

        return EvaluationOutput(
            grade=overall_grade,
            confidence_score=decimal.Decimal(str(grading_result["overall_confidence"])),
            evidence_mappings=evidence_mappings,
            flags=flag_result["flags"],
            strengths=strengths,
            gaps=gaps,
            reasoning_summary=grading_result["reasoning"],
            feedback=feedback_result,
        )


def _build_evidence_mappings(
    evidence_results: list[ExtractedEvidence],
    transcript: list[TranscriptSegment],
) -> list[EvidenceMapping]:
    """Build EvidenceMapping objects from extracted evidence."""
    # Create a mapping from quote to segment IDs
    # This is a simplified version - in production you'd want fuzzy matching
    quote_to_segments: dict[str, list[str]] = {}
    for segment in transcript:
        content_lower = segment.content.lower()
        for evidence in evidence_results:
            for quote in evidence["quotes"]:
                if quote.lower() in content_lower:
                    if quote not in quote_to_segments:
                        quote_to_segments[quote] = []
                    quote_to_segments[quote].append(str(segment.segment_id))

    mappings: list[EvidenceMapping] = []
    for evidence in evidence_results:
        # Collect all segment IDs for this criterion's quotes
        segment_ids: list[str] = []
        for quote in evidence["quotes"]:
            segment_ids.extend(quote_to_segments.get(quote, []))

        # Deduplicate
        segment_ids = list(dict.fromkeys(segment_ids))

        mappings.append(
            EvidenceMapping(
                criterion_id=RubricCriterionID(evidence["criterion_id"]),
                segment_ids=segment_ids,
                evidence_summary="; ".join(evidence["quotes"][:3]) if evidence["quotes"] else None,
                strength=evidence["strength"],
                failure_modes_detected=evidence["failure_modes_detected"],
            )
        )

    return mappings


def _extract_strengths_and_gaps(
    evidence_results: list[ExtractedEvidence],
    grading_result: GradingResult,
    feedback_result: FeedbackResult,
) -> tuple[list[str], list[str]]:
    """Extract strengths and gaps from evaluation results."""
    strengths: list[str] = []
    gaps: list[str] = []

    # Use feedback as primary source
    strengths.extend(feedback_result["strengths"])
    gaps.extend(feedback_result["areas_for_growth"])

    # Supplement with evidence-based observations
    for evidence in evidence_results:
        if evidence["strength"] == "strong":
            strengths.append(f"Strong understanding of {evidence['criterion_name']}")
        elif evidence["strength"] == "none":
            gaps.append(f"Limited evidence for {evidence['criterion_name']}")

        for fm in evidence["failure_modes_detected"]:
            gaps.append(f"Misconception detected: {fm}")

    # Deduplicate while preserving order
    strengths = list(dict.fromkeys(strengths))
    gaps = list(dict.fromkeys(gaps))

    return strengths, gaps
