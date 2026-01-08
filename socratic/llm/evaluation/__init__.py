"""Evaluation pipeline for automated assessment grading."""

from .evidence import extract_evidence
from .feedback import generate_feedback
from .flagger import detect_flags
from .grader import grade_criteria
from .pipeline import EvaluationPipeline

__all__ = [
    "EvaluationPipeline",
    "extract_evidence",
    "grade_criteria",
    "detect_flags",
    "generate_feedback",
]
