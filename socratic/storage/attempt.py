from __future__ import annotations

import datetime
import decimal
import typing as t

import sqlalchemy as sqla

from socratic.core import di
from socratic.lib import NotSet
from socratic.model import AssessmentAttempt, AssignmentID, AttemptID, AttemptStatus, Grade, UserID

from . import Session
from .table import assessment_attempts


def get(
    attempt_id: AttemptID,
    *,
    session: Session = di.Provide["storage.persistent.session"],
) -> AssessmentAttempt | None:
    """Get an attempt by ID."""
    stmt = sqla.select(assessment_attempts.__table__).where(assessment_attempts.attempt_id == attempt_id)
    row = session.execute(stmt).mappings().one_or_none()
    return AssessmentAttempt(**row) if row else None


def find(
    *,
    assignment_id: AssignmentID | None = None,
    learner_id: UserID | None = None,
    status: AttemptStatus | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[AssessmentAttempt, ...]:
    """Find attempts matching criteria."""
    stmt = sqla.select(assessment_attempts.__table__)
    if assignment_id is not None:
        stmt = stmt.where(assessment_attempts.assignment_id == assignment_id)
    if learner_id is not None:
        stmt = stmt.where(assessment_attempts.learner_id == learner_id)
    if status is not None:
        stmt = stmt.where(assessment_attempts.status == status.value)
    rows = session.execute(stmt).mappings().all()
    return tuple(AssessmentAttempt(**row) for row in rows)


def create(
    *,
    assignment_id: AssignmentID,
    learner_id: UserID,
    status: AttemptStatus = AttemptStatus.NotStarted,
    session: Session = di.Provide["storage.persistent.session"],
) -> AssessmentAttempt:
    """Create a new attempt."""
    attempt_id = AttemptID()
    stmt = sqla.insert(assessment_attempts).values(
        attempt_id=attempt_id,
        assignment_id=assignment_id,
        learner_id=learner_id,
        status=status.value,
    )
    session.execute(stmt)
    session.flush()
    result = get(attempt_id, session=session)
    assert result is not None
    return result


def update(
    attempt_id: AttemptID,
    *,
    status: AttemptStatus | NotSet = NotSet(),
    started_at: datetime.datetime | None | NotSet = NotSet(),
    completed_at: datetime.datetime | None | NotSet = NotSet(),
    grade: Grade | None | NotSet = NotSet(),
    confidence_score: decimal.Decimal | None | NotSet = NotSet(),
    audio_url: str | None | NotSet = NotSet(),
    video_url: str | None | NotSet = NotSet(),
    session: Session = di.Provide["storage.persistent.session"],
) -> None:
    """Update an attempt.

    Uses NotSet sentinel for parameters where None may be a valid value.
    Call get() after if you need the updated entity.

    Raises:
        KeyError: If attempt_id does not correspond to an attempt
    """
    values: dict[str, t.Any] = {}
    if not isinstance(status, NotSet):
        values["status"] = status.value
    if not isinstance(started_at, NotSet):
        values["started_at"] = started_at
    if not isinstance(completed_at, NotSet):
        values["completed_at"] = completed_at
    if not isinstance(grade, NotSet):
        values["grade"] = grade.value if grade is not None else None
    if not isinstance(confidence_score, NotSet):
        values["confidence_score"] = confidence_score
    if not isinstance(audio_url, NotSet):
        values["audio_url"] = audio_url
    if not isinstance(video_url, NotSet):
        values["video_url"] = video_url

    if values:
        stmt = sqla.update(assessment_attempts).where(assessment_attempts.attempt_id == attempt_id).values(**values)
    else:
        # No-op update to verify attempt exists
        stmt = (
            sqla
            .update(assessment_attempts)
            .where(assessment_attempts.attempt_id == attempt_id)
            .values(attempt_id=attempt_id)
        )

    result = session.execute(stmt)
    if result.rowcount == 0:  # pyright: ignore[reportAttributeAccessIssue]
        raise KeyError(f"Attempt {attempt_id} not found")

    session.flush()


def transition_to_evaluated(
    attempt_id: AttemptID,
    *,
    grade: Grade,
    confidence_score: decimal.Decimal,
    session: Session = di.Provide["storage.persistent.session"],
) -> AssessmentAttempt:
    """Transition an attempt from Completed to Evaluated status.

    Raises:
        KeyError: If attempt_id does not correspond to an attempt
        ValueError: If attempt is not in Completed status
    """
    attempt = get(attempt_id, session=session)
    if attempt is None:
        raise KeyError(f"Attempt {attempt_id} not found")

    if attempt.status != AttemptStatus.Completed:
        msg = f"Cannot evaluate attempt with status {attempt.status.value}"
        raise ValueError(msg)

    update(
        attempt_id,
        status=AttemptStatus.Evaluated,
        grade=grade,
        confidence_score=confidence_score,
        session=session,
    )

    result = get(attempt_id, session=session)
    assert result is not None
    return result


def transition_to_reviewed(
    attempt_id: AttemptID,
    *,
    grade_override: Grade | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> AssessmentAttempt:
    """Transition an attempt from Evaluated to Reviewed status.

    Raises:
        KeyError: If attempt_id does not correspond to an attempt
        ValueError: If attempt is not in Evaluated status
    """
    attempt = get(attempt_id, session=session)
    if attempt is None:
        raise KeyError(f"Attempt {attempt_id} not found")

    if attempt.status != AttemptStatus.Evaluated:
        msg = f"Cannot review attempt with status {attempt.status.value}"
        raise ValueError(msg)

    if grade_override is not None:
        update(
            attempt_id,
            status=AttemptStatus.Reviewed,
            grade=grade_override,
            session=session,
        )
    else:
        update(
            attempt_id,
            status=AttemptStatus.Reviewed,
            session=session,
        )

    result = get(attempt_id, session=session)
    assert result is not None
    return result
