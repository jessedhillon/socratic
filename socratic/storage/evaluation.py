from __future__ import annotations

import typing as t

import sqlalchemy as sqla

from socratic.core import di
from socratic.model import AssessmentFlag, AttemptID, EvaluationResult, EvaluationResultID, EvidenceMapping, \
    OrganizationID

from . import Session
from .table import evaluation_results


@t.overload
def get(
    evaluation_id: EvaluationResultID,
    *,
    session: Session = ...,
) -> EvaluationResult | None: ...


@t.overload
def get(
    evaluation_id: None = None,
    *,
    attempt_id: AttemptID,
    session: Session = ...,
) -> EvaluationResult | None: ...


def get(
    evaluation_id: EvaluationResultID | None = None,
    *,
    attempt_id: AttemptID | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> EvaluationResult | None:
    """Get an evaluation result by ID or attempt_id.

    Exactly one lookup key must be provided.
    """
    if evaluation_id is not None:
        stmt = sqla.select(evaluation_results.__table__).where(evaluation_results.evaluation_id == evaluation_id)
    elif attempt_id is not None:
        stmt = sqla.select(evaluation_results.__table__).where(evaluation_results.attempt_id == attempt_id)
    else:
        raise ValueError("exactly one of evaluation_id or attempt_id must be provided")

    row = session.execute(stmt).mappings().one_or_none()
    return EvaluationResult(**row) if row else None


def find_pending_review(
    *,
    organization_id: OrganizationID | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[EvaluationResult, ...]:
    """Find evaluations for attempts that need educator review.

    Returns evaluations for attempts with status='evaluated'.
    """
    from .table import assessment_attempts, assignments

    # Join evaluations -> attempts -> assignments to filter by org
    stmt = (
        sqla
        .select(evaluation_results.__table__)
        .join(
            assessment_attempts,
            evaluation_results.attempt_id == assessment_attempts.attempt_id,
        )
        .where(assessment_attempts.status == "evaluated")
        .order_by(assessment_attempts.completed_at.desc())
    )

    if organization_id is not None:
        stmt = stmt.join(
            assignments,
            assessment_attempts.assignment_id == assignments.assignment_id,
        ).where(assignments.organization_id == organization_id)

    rows = session.execute(stmt).mappings().all()
    return tuple(EvaluationResult(**row) for row in rows)


def create(
    *,
    attempt_id: AttemptID,
    evidence_mappings: list[EvidenceMapping] | None = None,
    flags: list[AssessmentFlag] | None = None,
    strengths: list[str] | None = None,
    gaps: list[str] | None = None,
    reasoning_summary: str | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> EvaluationResult:
    """Create a new evaluation result."""
    evidence_mappings_data: list[dict[str, t.Any]] = [em.model_dump() for em in (evidence_mappings or [])]
    flags_data: list[str] = [f.value for f in (flags or [])]

    evaluation_id = EvaluationResultID()
    stmt = sqla.insert(evaluation_results).values(
        evaluation_id=evaluation_id,
        attempt_id=attempt_id,
        evidence_mappings=evidence_mappings_data,
        flags=flags_data,
        strengths=strengths if strengths is not None else [],
        gaps=gaps if gaps is not None else [],
        reasoning_summary=reasoning_summary,
    )
    session.execute(stmt)
    session.flush()
    result = get(evaluation_id, session=session)
    assert result is not None
    return result
