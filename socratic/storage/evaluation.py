from __future__ import annotations

import typing as t

from sqlalchemy import select

from socratic.core import di
from socratic.model import AssessmentFlag, AttemptID, EvaluationResult, EvaluationResultID, EvidenceMapping, \
    OrganizationID

from . import Session
from .table import evaluation_results


def get(
    key: EvaluationResultID, session: Session = di.Provide["storage.persistent.session"]
) -> EvaluationResult | None:
    stmt = select(evaluation_results.__table__).where(evaluation_results.evaluation_id == key)
    row = session.execute(stmt).mappings().one_or_none()
    return EvaluationResult(**row) if row else None


def get_by_attempt(
    attempt_id: AttemptID, session: Session = di.Provide["storage.persistent.session"]
) -> EvaluationResult | None:
    stmt = select(evaluation_results.__table__).where(evaluation_results.attempt_id == attempt_id)
    row = session.execute(stmt).mappings().one_or_none()
    return EvaluationResult(**row) if row else None


def create(
    params: EvaluationCreateParams, session: Session = di.Provide["storage.persistent.session"]
) -> EvaluationResult:
    evidence_mappings_data: list[dict[str, t.Any]] = [m.model_dump() for m in params.get("evidence_mappings", [])]
    flags_data: list[str] = [f.value for f in params.get("flags", [])]

    evaluation = evaluation_results(
        evaluation_id=EvaluationResultID(),
        attempt_id=params["attempt_id"],
        evidence_mappings=evidence_mappings_data,
        flags=flags_data,
        strengths=params.get("strengths", []),
        gaps=params.get("gaps", []),
        reasoning_summary=params.get("reasoning_summary"),
    )
    session.add(evaluation)
    session.flush()
    return get(evaluation.evaluation_id, session=session)  # type: ignore


class EvaluationCreateParams(t.TypedDict, total=False):
    attempt_id: t.Required[AttemptID]
    evidence_mappings: list[EvidenceMapping]
    flags: list[AssessmentFlag]
    strengths: list[str]
    gaps: list[str]
    reasoning_summary: str | None


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
        select(evaluation_results.__table__)
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
