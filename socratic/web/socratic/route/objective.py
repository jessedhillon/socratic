"""Objective management routes."""

from __future__ import annotations

import typing as t

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from socratic.auth import AuthContext, require_educator
from socratic.core import di
from socratic.model import ObjectiveID, ObjectiveStatus
from socratic.storage import objective as obj_storage
from socratic.storage import rubric as rubric_storage
from socratic.storage.rubric import FailureModeCreateParams, GradeThresholdCreateParams

from ..view.objective import FailureModeResponse, GradeThresholdResponse, ObjectiveCreateRequest, \
    ObjectiveListResponse, ObjectiveResponse, ObjectiveUpdateRequest, RubricCriterionCreateRequest, \
    RubricCriterionResponse

router = APIRouter(prefix="/api/objectives", tags=["objectives"])


def _build_objective_response(
    objective_id: ObjectiveID,
    session: Session,
) -> ObjectiveResponse:
    """Build a full objective response with rubric criteria."""
    obj = obj_storage.get(objective_id, session=session)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Objective not found",
        )

    criteria = rubric_storage.find(objective_id=objective_id, session=session)
    criteria_responses = [
        RubricCriterionResponse(
            criterion_id=c.criterion_id,
            objective_id=c.objective_id,
            name=c.name,
            description=c.description,
            evidence_indicators=c.evidence_indicators,
            failure_modes=[
                FailureModeResponse(
                    name=fm.name,
                    description=fm.description,
                    indicators=fm.indicators,
                )
                for fm in c.failure_modes
            ],
            grade_thresholds=[
                GradeThresholdResponse(
                    grade=gt.grade,
                    description=gt.description,
                    min_evidence_count=gt.min_evidence_count,
                )
                for gt in c.grade_thresholds
            ],
            weight=c.weight,
        )
        for c in criteria
    ]

    return ObjectiveResponse(
        objective_id=obj.objective_id,
        organization_id=obj.organization_id,
        created_by=obj.created_by,
        title=obj.title,
        description=obj.description,
        scope_boundaries=obj.scope_boundaries,
        time_expectation_minutes=obj.time_expectation_minutes,
        initial_prompts=obj.initial_prompts,
        challenge_prompts=obj.challenge_prompts,
        extension_policy=obj.extension_policy,
        status=obj.status,
        create_time=obj.create_time,
        update_time=obj.update_time,
        rubric_criteria=criteria_responses,
    )


@router.post("", operation_id="create_objective", status_code=status.HTTP_201_CREATED)
@di.inject
def create_objective(
    request: ObjectiveCreateRequest,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> ObjectiveResponse:
    """Create a new objective with optional rubric criteria.

    Only educators can create objectives.
    """
    # Create the objective
    obj = obj_storage.create(
        organization_id=auth.organization_id,
        created_by=auth.user.user_id,
        title=request.title,
        description=request.description,
        scope_boundaries=request.scope_boundaries,
        time_expectation_minutes=request.time_expectation_minutes,
        initial_prompts=request.initial_prompts,
        challenge_prompts=request.challenge_prompts,
        extension_policy=request.extension_policy,
        session=session,
    )

    # Create rubric criteria if provided
    for criterion_req in request.rubric_criteria:
        rubric_storage.create(
            objective_id=obj.objective_id,
            name=criterion_req.name,
            description=criterion_req.description,
            evidence_indicators=criterion_req.evidence_indicators,
            failure_modes=[
                FailureModeCreateParams(
                    name=fm.name,
                    description=fm.description,
                    indicators=fm.indicators,
                )
                for fm in criterion_req.failure_modes
            ],
            grade_thresholds=[
                GradeThresholdCreateParams(
                    grade=gt.grade,
                    description=gt.description,
                    min_evidence_count=gt.min_evidence_count,
                )
                for gt in criterion_req.grade_thresholds
            ],
            weight=criterion_req.weight,
            session=session,
        )

    session.commit()
    return _build_objective_response(obj.objective_id, session)


@router.get("", operation_id="list_objectives")
@di.inject
def list_objectives(
    auth: AuthContext = Depends(require_educator),
    status_filter: ObjectiveStatus | None = None,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> ObjectiveListResponse:
    """List objectives for the educator's organization.

    Only educators can list objectives.
    """
    objectives = obj_storage.find(
        organization_id=auth.organization_id,
        status=status_filter,
        session=session,
    )

    # Build full responses with rubric criteria
    objective_responses = [_build_objective_response(obj.objective_id, session) for obj in objectives]

    return ObjectiveListResponse(
        objectives=objective_responses,
        total=len(objective_responses),
    )


@router.get("/{objective_id}", operation_id="get_objective")
@di.inject
def get_objective(
    objective_id: ObjectiveID,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> ObjectiveResponse:
    """Get objective details.

    Only educators can view objective details.
    """
    obj = obj_storage.get(objective_id, session=session)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Objective not found",
        )

    # Verify organization access
    if obj.organization_id != auth.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access objectives from other organizations",
        )

    return _build_objective_response(objective_id, session)


@router.put("/{objective_id}", operation_id="update_objective")
@di.inject
def update_objective(
    objective_id: ObjectiveID,
    request: ObjectiveUpdateRequest,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> ObjectiveResponse:
    """Update an objective.

    Only educators can update objectives.
    """
    obj = obj_storage.get(objective_id, session=session)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Objective not found",
        )

    # Verify organization access
    if obj.organization_id != auth.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update objectives from other organizations",
        )

    # Build update kwargs from request (only include fields that are set)
    update_kwargs: dict[str, t.Any] = {}
    if request.title is not None:
        update_kwargs["title"] = request.title
    if request.description is not None:
        update_kwargs["description"] = request.description
    if request.scope_boundaries is not None:
        update_kwargs["scope_boundaries"] = request.scope_boundaries
    if request.time_expectation_minutes is not None:
        update_kwargs["time_expectation_minutes"] = request.time_expectation_minutes
    if request.initial_prompts is not None:
        update_kwargs["initial_prompts"] = request.initial_prompts
    if request.challenge_prompts is not None:
        update_kwargs["challenge_prompts"] = request.challenge_prompts
    if request.extension_policy is not None:
        update_kwargs["extension_policy"] = request.extension_policy
    if request.status is not None:
        update_kwargs["status"] = request.status

    obj_storage.update(objective_id, **update_kwargs, session=session)
    session.commit()

    return _build_objective_response(objective_id, session)


@router.delete("/{objective_id}", operation_id="archive_objective")
@di.inject
def archive_objective(
    objective_id: ObjectiveID,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> ObjectiveResponse:
    """Archive an objective (soft delete).

    Only educators can archive objectives.
    """
    obj = obj_storage.get(objective_id, session=session)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Objective not found",
        )

    # Verify organization access
    if obj.organization_id != auth.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot archive objectives from other organizations",
        )

    obj_storage.update(objective_id, status=ObjectiveStatus.Archived, session=session)
    session.commit()

    return _build_objective_response(objective_id, session)


@router.post(
    "/{objective_id}/criteria",
    operation_id="add_rubric_criterion",
    status_code=status.HTTP_201_CREATED,
)
@di.inject
def add_rubric_criterion(
    objective_id: ObjectiveID,
    request: RubricCriterionCreateRequest,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> RubricCriterionResponse:
    """Add a rubric criterion to an objective.

    Only educators can add rubric criteria.
    """
    obj = obj_storage.get(objective_id, session=session)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Objective not found",
        )

    # Verify organization access
    if obj.organization_id != auth.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify objectives from other organizations",
        )

    criterion = rubric_storage.create(
        objective_id=objective_id,
        name=request.name,
        description=request.description,
        evidence_indicators=request.evidence_indicators,
        failure_modes=[
            FailureModeCreateParams(
                name=fm.name,
                description=fm.description,
                indicators=fm.indicators,
            )
            for fm in request.failure_modes
        ],
        grade_thresholds=[
            GradeThresholdCreateParams(
                grade=gt.grade,
                description=gt.description,
                min_evidence_count=gt.min_evidence_count,
            )
            for gt in request.grade_thresholds
        ],
        weight=request.weight,
        session=session,
    )

    session.commit()

    return RubricCriterionResponse(
        criterion_id=criterion.criterion_id,
        objective_id=criterion.objective_id,
        name=criterion.name,
        description=criterion.description,
        evidence_indicators=criterion.evidence_indicators,
        failure_modes=[
            FailureModeResponse(
                name=fm.name,
                description=fm.description,
                indicators=fm.indicators,
            )
            for fm in criterion.failure_modes
        ],
        grade_thresholds=[
            GradeThresholdResponse(
                grade=gt.grade,
                description=gt.description,
                min_evidence_count=gt.min_evidence_count,
            )
            for gt in criterion.grade_thresholds
        ],
        weight=criterion.weight,
    )
