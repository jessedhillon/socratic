"""Objective management routes."""

from __future__ import annotations

import typing as t

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from socratic.auth import AuthContext, require_educator
from socratic.core import di
from socratic.model import ObjectiveID, ObjectiveStatus, RubricCriterionID
from socratic.storage import objective as obj_storage
from socratic.storage import rubric as rubric_storage
from socratic.storage.rubric import ProficiencyLevelCreateParams

from ..view.objective import ObjectiveCreateRequest, ObjectiveListResponse, ObjectiveResponse, ObjectiveUpdateRequest, \
    ProficiencyLevelResponse, RubricCriterionCreateRequest, RubricCriterionResponse, RubricCriterionUpdateRequest

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
            proficiency_levels=[
                ProficiencyLevelResponse(
                    grade=pl.grade,
                    description=pl.description,
                )
                for pl in c.proficiency_levels
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
    with session.begin():
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
                proficiency_levels=[
                    ProficiencyLevelCreateParams(
                        grade=pl.grade,
                        description=pl.description,
                    )
                    for pl in criterion_req.proficiency_levels
                ],
                weight=criterion_req.weight,
                session=session,
            )

        return _build_objective_response(obj.objective_id, session)


@router.get("", operation_id="list_objectives")
@di.inject
def list_objectives(
    auth: AuthContext = Depends(require_educator),
    status_filter: ObjectiveStatus | None = None,
    include_archived: bool = False,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> ObjectiveListResponse:
    """List objectives for the educator's organization.

    Only educators can list objectives.
    Archived objectives are excluded by default unless include_archived=True.
    """
    with session.begin():
        objectives = obj_storage.find(
            organization_id=auth.organization_id,
            status=status_filter,
            session=session,
        )

        # Filter out archived objectives unless explicitly requested
        if not include_archived and status_filter is None:
            objectives = tuple(o for o in objectives if o.status != ObjectiveStatus.Archived)

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
    with session.begin():
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
    with session.begin():
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
    with session.begin():
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
    with session.begin():
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
            proficiency_levels=[
                ProficiencyLevelCreateParams(
                    grade=pl.grade,
                    description=pl.description,
                )
                for pl in request.proficiency_levels
            ],
            weight=request.weight,
            session=session,
        )

        return RubricCriterionResponse(
            criterion_id=criterion.criterion_id,
            objective_id=criterion.objective_id,
            name=criterion.name,
            description=criterion.description,
            proficiency_levels=[
                ProficiencyLevelResponse(
                    grade=pl.grade,
                    description=pl.description,
                )
                for pl in criterion.proficiency_levels
            ],
            weight=criterion.weight,
        )


@router.put(
    "/{objective_id}/criteria/{criterion_id}",
    operation_id="update_rubric_criterion",
)
@di.inject
def update_rubric_criterion(
    objective_id: ObjectiveID,
    criterion_id: RubricCriterionID,
    request: RubricCriterionUpdateRequest,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> RubricCriterionResponse:
    """Update a rubric criterion.

    Only educators can update rubric criteria.
    """
    with session.begin():
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

        # Verify criterion exists and belongs to this objective
        criterion = rubric_storage.get(criterion_id, session=session)
        if criterion is None or criterion.objective_id != objective_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rubric criterion not found",
            )

        # Build update kwargs from request (only include fields that are set)
        update_kwargs: dict[str, t.Any] = {}
        if request.name is not None:
            update_kwargs["name"] = request.name
        if request.description is not None:
            update_kwargs["description"] = request.description
        if request.proficiency_levels is not None:
            update_kwargs["proficiency_levels"] = [
                ProficiencyLevelCreateParams(
                    grade=pl.grade,
                    description=pl.description,
                )
                for pl in request.proficiency_levels
            ]
        if request.weight is not None:
            update_kwargs["weight"] = request.weight

        rubric_storage.update(criterion_id, **update_kwargs, session=session)

        # Fetch the updated criterion
        updated = rubric_storage.get(criterion_id, session=session)
        assert updated is not None

        return RubricCriterionResponse(
            criterion_id=updated.criterion_id,
            objective_id=updated.objective_id,
            name=updated.name,
            description=updated.description,
            proficiency_levels=[
                ProficiencyLevelResponse(
                    grade=pl.grade,
                    description=pl.description,
                )
                for pl in updated.proficiency_levels
            ],
            weight=updated.weight,
        )


@router.delete(
    "/{objective_id}/criteria/{criterion_id}",
    operation_id="delete_rubric_criterion",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
@di.inject
def delete_rubric_criterion(
    objective_id: ObjectiveID,
    criterion_id: RubricCriterionID,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> None:
    """Delete a rubric criterion.

    Only educators can delete rubric criteria.
    """
    with session.begin():
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

        # Verify criterion exists and belongs to this objective
        criterion = rubric_storage.get(criterion_id, session=session)
        if criterion is None or criterion.objective_id != objective_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rubric criterion not found",
            )

        rubric_storage.delete(criterion_id, session=session)
