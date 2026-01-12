"""Educator review API routes."""

from __future__ import annotations

import typing as t

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from socratic.auth.middleware import AuthContext, require_educator
from socratic.core import di
from socratic.model import AttemptID, AttemptStatus, Grade
from socratic.storage import assignment as assignment_storage
from socratic.storage import attempt as attempt_storage
from socratic.storage import evaluation as eval_storage
from socratic.storage import objective as obj_storage
from socratic.storage import override as override_storage
from socratic.storage import rubric as rubric_storage
from socratic.storage import transcript as transcript_storage
from socratic.storage import user as user_storage

from ..view.review import AttemptResponse, EvaluationResponse, EvidenceMappingResponse, FeedbackRequest, \
    GradeAcceptRequest, GradeOverrideRequest, OverrideResponse, ReviewDetailResponse, ReviewListResponse, \
    ReviewSummary, TranscriptSegmentResponse

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.get("", operation_id="list_pending_reviews")
@di.inject
def list_pending_reviews(
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> ReviewListResponse:
    """List all attempts pending educator review."""
    with session.begin():
        # Get evaluations for attempts with status=Evaluated in educator's org
        evaluations = eval_storage.find_pending_review(
            organization_id=auth.organization_id,
            session=session,
        )

        reviews: list[ReviewSummary] = []
        for evaluation in evaluations:
            # Get the attempt
            attempt = attempt_storage.get(evaluation.attempt_id, session=session)
            if attempt is None:
                continue

            # Get the assignment and objective
            assignment = assignment_storage.get(attempt.assignment_id, session=session)
            if assignment is None:
                continue

            objective = obj_storage.get(assignment.objective_id, session=session)
            if objective is None:
                continue

            # Get learner name
            learner = user_storage.get(user_id=attempt.learner_id, session=session)
            learner_name = learner.name if learner else None

            reviews.append(
                ReviewSummary(
                    attempt_id=attempt.attempt_id,
                    learner_id=attempt.learner_id,
                    learner_name=learner_name,
                    objective_id=objective.objective_id,
                    objective_title=objective.title,
                    grade=attempt.grade,
                    confidence_score=attempt.confidence_score,
                    flags=evaluation.flags,
                    completed_at=attempt.completed_at,
                )
            )

        return ReviewListResponse(reviews=reviews, total=len(reviews))


@router.get("/{attempt_id}", operation_id="get_review_detail")
@di.inject
def get_review_detail(
    attempt_id: AttemptID,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> ReviewDetailResponse:
    """Get full review detail for an attempt."""
    with session.begin():
        # Get the attempt
        attempt = attempt_storage.get(attempt_id, session=session)
        if attempt is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")

        # Get assignment and verify org access
        assignment = assignment_storage.get(attempt.assignment_id, session=session)
        if assignment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

        if assignment.organization_id != auth.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access reviews from other organizations",
            )

        # Get objective
        objective = obj_storage.get(assignment.objective_id, session=session)
        if objective is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objective not found")

        # Get rubric criteria for mapping names
        criteria = rubric_storage.find(objective_id=objective.objective_id, session=session)
        criteria_by_id = {str(c.criterion_id): c for c in criteria}

        # Get evaluation
        evaluation = eval_storage.get(attempt_id=attempt_id, session=session)

        # Get transcript
        transcript_segments = transcript_storage.find(attempt_id=attempt_id, session=session)

        # Get override history
        overrides = override_storage.find(attempt_id=attempt_id, session=session)

        # Get learner name
        learner = user_storage.get(user_id=attempt.learner_id, session=session)
        learner_name = learner.name if learner else None

        # Build response
        return _build_review_detail(
            attempt=attempt,
            learner_name=learner_name,
            evaluation=evaluation,
            transcript_segments=transcript_segments,
            overrides=overrides,
            objective=objective,
            criteria_by_id=criteria_by_id,
            session=session,
        )


@router.post("/{attempt_id}/accept", operation_id="accept_grade")
@di.inject
def accept_grade(
    attempt_id: AttemptID,
    request: GradeAcceptRequest,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> ReviewDetailResponse:
    """Accept the AI-assigned grade and mark as reviewed."""
    with session.begin():
        # Validate attempt and access
        attempt, _, _ = _validate_review_access(attempt_id, auth, session)

        # Validate status
        if attempt.status != AttemptStatus.Evaluated:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot accept grade for attempt with status {attempt.status.value}",
            )

        # Transition to reviewed
        attempt_storage.transition_to_reviewed(attempt_id, session=session)

    # Return updated review detail
    return get_review_detail(attempt_id, auth, session)


@router.post("/{attempt_id}/override", operation_id="override_grade")
@di.inject
def override_grade(
    attempt_id: AttemptID,
    request: GradeOverrideRequest,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> ReviewDetailResponse:
    """Override the AI-assigned grade with educator's judgment."""
    with session.begin():
        # Validate attempt and access
        attempt, _, _ = _validate_review_access(attempt_id, auth, session)

        # Validate status
        if attempt.status != AttemptStatus.Evaluated:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot override grade for attempt with status {attempt.status.value}",
            )

        # Create override record
        override_storage.create(
            attempt_id=attempt_id,
            educator_id=auth.user.user_id,
            original_grade=attempt.grade,
            new_grade=request.new_grade,
            reason=request.reason,
            session=session,
        )

        # Transition to reviewed with new grade
        attempt_storage.transition_to_reviewed(
            attempt_id,
            grade_override=request.new_grade,
            session=session,
        )

    # Return updated review detail
    return get_review_detail(attempt_id, auth, session)


@router.post("/{attempt_id}/feedback", operation_id="add_feedback")
@di.inject
def add_feedback(
    attempt_id: AttemptID,
    request: FeedbackRequest,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> ReviewDetailResponse:
    """Add qualitative feedback to a reviewed attempt."""
    with session.begin():
        # Validate attempt and access
        attempt, _, _ = _validate_review_access(attempt_id, auth, session)

        # Create or update feedback via override record
        # Using override for feedback storage allows tracking history
        override_storage.create(
            attempt_id=attempt_id,
            educator_id=auth.user.user_id,
            original_grade=attempt.grade,
            new_grade=attempt.grade or Grade.F,  # Keep same grade
            reason="Feedback added",
            feedback=request.feedback_text,
            session=session,
        )

    # Return updated review detail
    return get_review_detail(attempt_id, auth, session)


def _validate_review_access(
    attempt_id: AttemptID,
    auth: AuthContext,
    session: Session,
) -> tuple[t.Any, t.Any, t.Any]:
    """Validate that the educator can access this review."""
    attempt = attempt_storage.get(attempt_id, session=session)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")

    assignment = assignment_storage.get(attempt.assignment_id, session=session)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    if assignment.organization_id != auth.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access reviews from other organizations",
        )

    objective = obj_storage.get(assignment.objective_id, session=session)
    if objective is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objective not found")

    return attempt, assignment, objective


def _build_review_detail(
    attempt: t.Any,
    learner_name: str | None,
    evaluation: t.Any,
    transcript_segments: tuple[t.Any, ...],
    overrides: tuple[t.Any, ...],
    objective: t.Any,
    criteria_by_id: dict[str, t.Any],
    session: Session,
) -> ReviewDetailResponse:
    """Build the full review detail response."""
    # Build attempt response
    attempt_response = AttemptResponse(
        attempt_id=attempt.attempt_id,
        learner_id=attempt.learner_id,
        learner_name=learner_name,
        status=attempt.status,
        started_at=attempt.started_at,
        completed_at=attempt.completed_at,
        grade=attempt.grade,
        confidence_score=attempt.confidence_score,
    )

    # Build evaluation response
    evaluation_response = None
    if evaluation is not None:
        evidence_mappings: list[EvidenceMappingResponse] = []
        for mapping in evaluation.evidence_mappings:
            criterion = criteria_by_id.get(str(mapping.criterion_id))
            criterion_name = criterion.name if criterion else None
            evidence_mappings.append(
                EvidenceMappingResponse(
                    criterion_id=mapping.criterion_id,
                    criterion_name=criterion_name,
                    segment_ids=mapping.segment_ids,
                    evidence_summary=mapping.evidence_summary,
                    strength=mapping.strength,
                    failure_modes_detected=mapping.failure_modes_detected,
                )
            )

        evaluation_response = EvaluationResponse(
            evaluation_id=evaluation.evaluation_id,
            evidence_mappings=evidence_mappings,
            flags=evaluation.flags,
            strengths=evaluation.strengths,
            gaps=evaluation.gaps,
            reasoning_summary=evaluation.reasoning_summary,
            create_time=evaluation.create_time,
        )

    # Build transcript response
    transcript_response = [
        TranscriptSegmentResponse(
            segment_id=seg.segment_id,
            utterance_type=seg.utterance_type,
            content=seg.content,
            start_time=seg.start_time,
            prompt_index=seg.prompt_index,
        )
        for seg in transcript_segments
    ]

    # Build override history
    override_history: list[OverrideResponse] = []
    for override in overrides:
        educator = user_storage.get(user_id=override.educator_id, session=session)
        educator_name = educator.name if educator else None
        override_history.append(
            OverrideResponse(
                override_id=override.override_id,
                educator_id=override.educator_id,
                educator_name=educator_name,
                original_grade=override.original_grade,
                new_grade=override.new_grade,
                reason=override.reason,
                feedback=override.feedback,
                create_time=override.create_time,
            )
        )

    return ReviewDetailResponse(
        attempt=attempt_response,
        evaluation=evaluation_response,
        transcript=transcript_response,
        override_history=override_history,
        objective_id=objective.objective_id,
        objective_title=objective.title,
        objective_description=objective.description,
    )
