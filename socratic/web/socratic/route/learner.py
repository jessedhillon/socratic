"""Learner management and dashboard routes."""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from socratic.auth import AuthContext, require_educator, require_learner
from socratic.core import di
from socratic.model import AssignmentID, AttemptStatus, UserID, UserRole
from socratic.storage import assignment as assignment_storage
from socratic.storage import attempt as attempt_storage
from socratic.storage import objective as obj_storage
from socratic.storage import strand as strand_storage
from socratic.storage import user as user_storage

from ..view.assignment import AssignmentWithAttemptsResponse, AttemptResponse, LearnerAssignmentSummary, \
    LearnerDashboardResponse, LearnerListResponse, LearnerResponse

router = APIRouter(prefix="/api/learners", tags=["learners"])


@router.get("", operation_id="list_learners")
@di.inject
def list_learners(
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> LearnerListResponse:
    """List all learners in the organization.

    Only educators can list learners.
    """
    with session.begin():
        users = user_storage.find(
            organization_id=auth.organization_id,
            role=UserRole.Learner,
            session=session,
        )

        learners = [
            LearnerResponse(
                user_id=user.user_id,
                email=user.email,
                name=user.name,
            )
            for user in users
        ]

        return LearnerListResponse(
            learners=learners,
            total=len(learners),
        )


@router.get("/{learner_id}/assignments", operation_id="get_learner_assignments")
@di.inject
def get_learner_assignments(
    learner_id: UserID,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> list[AssignmentWithAttemptsResponse]:
    """Get all assignments for a specific learner.

    Only educators can view learner assignments.
    """
    with session.begin():
        # Verify learner exists and belongs to organization
        learner = user_storage.get(learner_id, session=session)
        if learner is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learner not found",
            )

        memberships = user_storage.get_memberships(learner_id, session=session)
        if not any(m.organization_id == auth.organization_id for m in memberships):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Learner is not in your organization",
            )

        # Get all assignments for this learner
        assignments = assignment_storage.find(
            organization_id=auth.organization_id,
            assigned_to=learner_id,
            session=session,
        )

        result: list[AssignmentWithAttemptsResponse] = []
        for assignment in assignments:
            attempts = attempt_storage.find(assignment_id=assignment.assignment_id, session=session)
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

            result.append(
                AssignmentWithAttemptsResponse(
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
            )

        return result


@router.get("/me/dashboard", operation_id="get_learner_dashboard")
@di.inject
def get_learner_dashboard(
    auth: AuthContext = Depends(require_learner),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> LearnerDashboardResponse:
    """Get the current learner's dashboard with all assignments.

    Shows assignment status, grades, and availability.
    """
    with session.begin():
        # Get all assignments for the current learner
        assignments = assignment_storage.find(
            organization_id=auth.organization_id,
            assigned_to=auth.user.user_id,
            session=session,
        )

        now = datetime.datetime.now(datetime.UTC)
        summaries: list[LearnerAssignmentSummary] = []
        total_completed = 0
        total_in_progress = 0
        total_pending = 0

        for assignment in assignments:
            # Get objective info
            objective = obj_storage.get(assignment.objective_id, session=session)
            if objective is None:
                continue

            # Get attempts for this assignment
            attempts = attempt_storage.find(assignment_id=assignment.assignment_id, session=session)
            attempts_used = len(attempts)
            attempts_remaining = max(0, assignment.max_attempts - attempts_used)

            # Determine current status
            latest_attempt = max(attempts, key=lambda a: a.create_time) if attempts else None

            if latest_attempt is None:
                current_status = AttemptStatus.NotStarted
                total_pending += 1
            elif latest_attempt.status in (AttemptStatus.Evaluated, AttemptStatus.Reviewed):
                current_status = AttemptStatus.Completed
                total_completed += 1
            elif latest_attempt.status == AttemptStatus.InProgress:
                current_status = AttemptStatus.InProgress
                total_in_progress += 1
            else:
                current_status = latest_attempt.status
                if current_status == AttemptStatus.NotStarted:
                    total_pending += 1

            # Determine availability
            is_available = True
            if assignment.available_from and now < assignment.available_from:
                is_available = False
            if assignment.available_until and now > assignment.available_until:
                is_available = False
            if attempts_remaining <= 0 and current_status != AttemptStatus.Completed:
                is_available = False

            # Check prerequisites (simplified - just check if dependency objectives are completed)
            is_locked = False
            dependencies = strand_storage.get_dependencies(assignment.objective_id, session=session)
            for dep in dependencies:
                # Find assignments for the prerequisite objective
                prereq_assignments = assignment_storage.find(
                    organization_id=auth.organization_id,
                    objective_id=dep.depends_on_objective_id,
                    assigned_to=auth.user.user_id,
                    session=session,
                )
                # Check if any prereq assignment is completed
                prereq_completed = False
                for prereq in prereq_assignments:
                    prereq_attempts = attempt_storage.find(assignment_id=prereq.assignment_id, session=session)
                    for prereq_attempt in prereq_attempts:
                        if prereq_attempt.status in (AttemptStatus.Evaluated, AttemptStatus.Reviewed):
                            prereq_completed = True
                            break
                    if prereq_completed:
                        break
                if not prereq_completed and dependencies:
                    is_locked = True
                    break

            # Get latest grade if available
            grade = latest_attempt.grade if latest_attempt else None

            summaries.append(
                LearnerAssignmentSummary(
                    assignment_id=assignment.assignment_id,
                    objective_id=assignment.objective_id,
                    objective_title=objective.title,
                    status=current_status,
                    grade=grade,
                    attempts_used=attempts_used,
                    attempts_remaining=attempts_remaining,
                    available_from=assignment.available_from,
                    available_until=assignment.available_until,
                    is_available=is_available and not is_locked,
                    is_locked=is_locked,
                )
            )

        return LearnerDashboardResponse(
            assignments=summaries,
            total_completed=total_completed,
            total_in_progress=total_in_progress,
            total_pending=total_pending,
        )


@router.get("/me/assignments/{assignment_id}", operation_id="get_my_assignment")
@di.inject
def get_my_assignment(
    assignment_id: str,
    auth: AuthContext = Depends(require_learner),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> AssignmentWithAttemptsResponse:
    """Get details of a specific assignment for the current learner."""
    with session.begin():
        aid = AssignmentID(assignment_id)
        assignment = assignment_storage.get(aid, session=session)
        if assignment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found",
            )

        # Verify this assignment belongs to the current learner
        if assignment.assigned_to != auth.user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This assignment is not yours",
            )

        attempts = attempt_storage.find(assignment_id=aid, session=session)
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
