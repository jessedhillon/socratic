from __future__ import annotations

import datetime
import decimal
import typing as t

from sqlalchemy import select

from socratic.core import di
from socratic.model import AssessmentAttempt, AssignmentID, AttemptID, AttemptStatus, Grade, UserID

from . import Session
from .table import assessment_attempts


def get(key: AttemptID, session: Session = di.Provide["storage.persistent.session"]) -> AssessmentAttempt | None:
    stmt = select(assessment_attempts.__table__).where(assessment_attempts.attempt_id == key)
    row = session.execute(stmt).mappings().one_or_none()
    return AssessmentAttempt(**row) if row else None


def find(
    *,
    assignment_id: AssignmentID | None = None,
    learner_id: UserID | None = None,
    status: AttemptStatus | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[AssessmentAttempt, ...]:
    stmt = select(assessment_attempts.__table__)
    if assignment_id is not None:
        stmt = stmt.where(assessment_attempts.assignment_id == assignment_id)
    if learner_id is not None:
        stmt = stmt.where(assessment_attempts.learner_id == learner_id)
    if status is not None:
        stmt = stmt.where(assessment_attempts.status == status.value)
    rows = session.execute(stmt).mappings().all()
    return tuple(AssessmentAttempt(**row) for row in rows)


def create(
    params: AttemptCreateParams, session: Session = di.Provide["storage.persistent.session"]
) -> AssessmentAttempt:
    attempt = assessment_attempts(
        attempt_id=AttemptID(),
        assignment_id=params["assignment_id"],
        learner_id=params["learner_id"],
        status=params.get("status", AttemptStatus.NotStarted).value,
    )
    session.add(attempt)
    session.flush()
    return get(attempt.attempt_id, session=session)  # type: ignore


def update(
    key: AttemptID,
    params: AttemptUpdateParams,
    session: Session = di.Provide["storage.persistent.session"],
) -> AssessmentAttempt | None:
    stmt = select(assessment_attempts).where(assessment_attempts.attempt_id == key)
    attempt = session.execute(stmt).scalar_one_or_none()
    if attempt is None:
        return None
    for field, value in params.items():
        if value is not None:
            actual_value: t.Any = value
            if field in ("status", "grade") and hasattr(value, "value"):
                actual_value = value.value  # type: ignore[union-attr]
            setattr(attempt, field, actual_value)
    session.flush()
    return get(key, session=session)


class AttemptCreateParams(t.TypedDict, total=False):
    assignment_id: t.Required[AssignmentID]
    learner_id: t.Required[UserID]
    status: AttemptStatus


class AttemptUpdateParams(t.TypedDict, total=False):
    status: AttemptStatus
    started_at: datetime.datetime | None
    completed_at: datetime.datetime | None
    grade: Grade | None
    confidence_score: decimal.Decimal | None
    audio_url: str | None


def transition_to_evaluated(
    attempt_id: AttemptID,
    grade: Grade,
    confidence_score: decimal.Decimal,
    session: Session = di.Provide["storage.persistent.session"],
) -> AssessmentAttempt | None:
    """Transition an attempt from Completed to Evaluated status.

    Args:
        attempt_id: The attempt to transition
        grade: The AI-assigned grade
        confidence_score: Confidence in the grade (0-1)
        session: Database session

    Returns:
        Updated attempt or None if not found
    """
    attempt = get(attempt_id, session=session)
    if attempt is None:
        return None

    # Validate current status
    if attempt.status != AttemptStatus.Completed:
        msg = f"Cannot evaluate attempt with status {attempt.status.value}"
        raise ValueError(msg)

    return update(
        attempt_id,
        {
            "status": AttemptStatus.Evaluated,
            "grade": grade,
            "confidence_score": confidence_score,
        },
        session=session,
    )


def transition_to_reviewed(
    attempt_id: AttemptID,
    *,
    grade_override: Grade | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> AssessmentAttempt | None:
    """Transition an attempt from Evaluated to Reviewed status.

    Args:
        attempt_id: The attempt to transition
        grade_override: Optional new grade if educator overrides
        session: Database session

    Returns:
        Updated attempt or None if not found
    """
    attempt = get(attempt_id, session=session)
    if attempt is None:
        return None

    # Validate current status
    if attempt.status != AttemptStatus.Evaluated:
        msg = f"Cannot review attempt with status {attempt.status.value}"
        raise ValueError(msg)

    update_params: AttemptUpdateParams = {"status": AttemptStatus.Reviewed}
    if grade_override is not None:
        update_params["grade"] = grade_override

    return update(attempt_id, update_params, session=session)
