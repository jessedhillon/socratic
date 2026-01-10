"""Assignment management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from socratic.auth import AuthContext, require_educator
from socratic.core import di
from socratic.model import AssignmentID, ObjectiveID, UserID
from socratic.storage import assignment as assignment_storage
from socratic.storage import attempt as attempt_storage
from socratic.storage import objective as obj_storage
from socratic.storage import user as user_storage

from ..view.assignment import AssignmentCreateRequest, AssignmentListResponse, AssignmentResponse, \
    AssignmentUpdateRequest, AssignmentWithAttemptsResponse, AttemptResponse, BulkAssignmentCreateRequest

router = APIRouter(prefix="/api/assignments", tags=["assignments"])


def _build_assignment_response(assignment_id: AssignmentID, session: Session) -> AssignmentResponse:
    """Build an assignment response."""
    assignment = assignment_storage.get(assignment_id, session=session)
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )
    return AssignmentResponse(
        assignment_id=assignment.assignment_id,
        organization_id=assignment.organization_id,
        objective_id=assignment.objective_id,
        assigned_by=assignment.assigned_by,
        assigned_to=assignment.assigned_to,
        available_from=assignment.available_from,
        available_until=assignment.available_until,
        max_attempts=assignment.max_attempts,
        retake_policy=assignment.retake_policy,
        retake_delay_hours=assignment.retake_delay_hours,
        create_time=assignment.create_time,
        update_time=assignment.update_time,
    )


def _build_assignment_with_attempts_response(
    assignment_id: AssignmentID, session: Session
) -> AssignmentWithAttemptsResponse:
    """Build an assignment response with attempts."""
    assignment = assignment_storage.get(assignment_id, session=session)
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )

    attempts = attempt_storage.find(assignment_id=assignment_id, session=session)
    attempt_responses = [
        AttemptResponse(
            attempt_id=a.attempt_id,
            assignment_id=a.assignment_id,
            learner_id=a.learner_id,
            status=a.status,
            started_at=a.started_at,
            completed_at=a.completed_at,
            grade=a.grade,
            confidence_score=a.confidence_score,
            create_time=a.create_time,
        )
        for a in attempts
    ]

    return AssignmentWithAttemptsResponse(
        assignment_id=assignment.assignment_id,
        organization_id=assignment.organization_id,
        objective_id=assignment.objective_id,
        assigned_by=assignment.assigned_by,
        assigned_to=assignment.assigned_to,
        available_from=assignment.available_from,
        available_until=assignment.available_until,
        max_attempts=assignment.max_attempts,
        retake_policy=assignment.retake_policy,
        retake_delay_hours=assignment.retake_delay_hours,
        create_time=assignment.create_time,
        update_time=assignment.update_time,
        attempts=attempt_responses,
        attempts_remaining=max(0, assignment.max_attempts - len(attempts)),
    )


@router.post("", operation_id="create_assignment", status_code=status.HTTP_201_CREATED)
@di.inject
def create_assignment(
    request: AssignmentCreateRequest,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> AssignmentResponse:
    """Create a new assignment for a learner.

    Only educators can create assignments.
    """
    # Verify objective exists and belongs to organization
    objective = obj_storage.get(request.objective_id, session=session)
    if objective is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Objective not found",
        )
    if objective.organization_id != auth.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot assign objectives from other organizations",
        )

    # Verify learner exists and belongs to organization
    learner = user_storage.get(request.assigned_to, session=session)
    if learner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learner not found",
        )
    memberships = user_storage.get_memberships(request.assigned_to, session=session)
    if not any(m.organization_id == auth.organization_id for m in memberships):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Learner is not in your organization",
        )

    assignment = assignment_storage.create(
        {
            "organization_id": auth.organization_id,
            "objective_id": request.objective_id,
            "assigned_by": auth.user.user_id,
            "assigned_to": request.assigned_to,
            "available_from": request.available_from,
            "available_until": request.available_until,
            "max_attempts": request.max_attempts,
            "retake_policy": request.retake_policy,
            "retake_delay_hours": request.retake_delay_hours,
        },
        session=session,
    )

    session.commit()
    return _build_assignment_response(assignment.assignment_id, session)


@router.post("/bulk", operation_id="create_bulk_assignments", status_code=status.HTTP_201_CREATED)
@di.inject
def create_bulk_assignments(
    request: BulkAssignmentCreateRequest,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> AssignmentListResponse:
    """Create assignments for multiple learners at once.

    Only educators can create assignments.
    """
    # Verify objective exists and belongs to organization
    objective = obj_storage.get(request.objective_id, session=session)
    if objective is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Objective not found",
        )
    if objective.organization_id != auth.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot assign objectives from other organizations",
        )

    created_assignments: list[AssignmentResponse] = []

    for learner_id in request.assigned_to:
        # Verify each learner exists and belongs to organization
        learner = user_storage.get(learner_id, session=session)
        if learner is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Learner {learner_id} not found",
            )
        memberships = user_storage.get_memberships(learner_id, session=session)
        if not any(m.organization_id == auth.organization_id for m in memberships):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Learner {learner_id} is not in your organization",
            )

        assignment = assignment_storage.create(
            {
                "organization_id": auth.organization_id,
                "objective_id": request.objective_id,
                "assigned_by": auth.user.user_id,
                "assigned_to": learner_id,
                "available_from": request.available_from,
                "available_until": request.available_until,
                "max_attempts": request.max_attempts,
                "retake_policy": request.retake_policy,
                "retake_delay_hours": request.retake_delay_hours,
            },
            session=session,
        )
        created_assignments.append(_build_assignment_response(assignment.assignment_id, session))

    session.commit()

    return AssignmentListResponse(
        assignments=created_assignments,
        total=len(created_assignments),
    )


@router.get("", operation_id="list_assignments")
@di.inject
def list_assignments(
    objective_id: ObjectiveID | None = None,
    assigned_to: UserID | None = None,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> AssignmentListResponse:
    """List assignments.

    Educators can filter by objective or learner.
    """
    assignments = assignment_storage.find(
        organization_id=auth.organization_id,
        objective_id=objective_id,
        assigned_to=assigned_to,
        session=session,
    )

    assignment_responses = [
        AssignmentResponse(
            assignment_id=a.assignment_id,
            organization_id=a.organization_id,
            objective_id=a.objective_id,
            assigned_by=a.assigned_by,
            assigned_to=a.assigned_to,
            available_from=a.available_from,
            available_until=a.available_until,
            max_attempts=a.max_attempts,
            retake_policy=a.retake_policy,
            retake_delay_hours=a.retake_delay_hours,
            create_time=a.create_time,
            update_time=a.update_time,
        )
        for a in assignments
    ]

    return AssignmentListResponse(
        assignments=assignment_responses,
        total=len(assignment_responses),
    )


@router.get("/{assignment_id}", operation_id="get_assignment")
@di.inject
def get_assignment(
    assignment_id: AssignmentID,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> AssignmentWithAttemptsResponse:
    """Get assignment details with attempts.

    Educators can view any assignment in their organization.
    """
    assignment = assignment_storage.get(assignment_id, session=session)
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )

    if assignment.organization_id != auth.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access assignments from other organizations",
        )

    return _build_assignment_with_attempts_response(assignment_id, session)


@router.put("/{assignment_id}", operation_id="update_assignment")
@di.inject
def update_assignment(
    assignment_id: AssignmentID,
    request: AssignmentUpdateRequest,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> AssignmentResponse:
    """Update an assignment.

    Only educators can update assignments.
    """
    assignment = assignment_storage.get(assignment_id, session=session)
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )

    if assignment.organization_id != auth.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update assignments from other organizations",
        )

    update_params: assignment_storage.AssignmentUpdateParams = {}
    if request.available_from is not None:
        update_params["available_from"] = request.available_from
    if request.available_until is not None:
        update_params["available_until"] = request.available_until
    if request.max_attempts is not None:
        update_params["max_attempts"] = request.max_attempts
    if request.retake_policy is not None:
        update_params["retake_policy"] = request.retake_policy
    if request.retake_delay_hours is not None:
        update_params["retake_delay_hours"] = request.retake_delay_hours
    assignment_storage.update(assignment_id, update_params, session=session)

    session.commit()
    return _build_assignment_response(assignment_id, session)


@router.delete(
    "/{assignment_id}", operation_id="cancel_assignment", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
@di.inject
def cancel_assignment(
    assignment_id: AssignmentID,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> None:
    """Cancel (delete) an assignment.

    Only educators can cancel assignments. This is a hard delete.
    """
    assignment = assignment_storage.get(assignment_id, session=session)
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )

    if assignment.organization_id != auth.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot cancel assignments from other organizations",
        )

    # Check if there are any attempts
    attempts = attempt_storage.find(assignment_id=assignment_id, session=session)
    if attempts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot cancel assignment with existing attempts",
        )

    assignment_storage.delete(assignment_id, session=session)
    session.commit()
