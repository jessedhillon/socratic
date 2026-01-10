"""Strand management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from socratic.auth import AuthContext, require_educator
from socratic.core import di
from socratic.model import ObjectiveID, StrandID
from socratic.storage import objective as obj_storage
from socratic.storage import strand as strand_storage
from socratic.storage.table import objectives_in_strands
from socratic.storage.table import strands as strands_table

from ..view.strand import ObjectiveDependencyRequest, ObjectiveDependencyResponse, ObjectiveInStrandRequest, \
    ObjectiveInStrandResponse, ReorderObjectivesRequest, StrandCreateRequest, StrandListResponse, StrandResponse, \
    StrandUpdateRequest, StrandWithObjectivesResponse

router = APIRouter(prefix="/api/strands", tags=["strands"])


def _build_strand_response(strand_id: StrandID, session: Session) -> StrandResponse:
    """Build a strand response."""
    strand = strand_storage.get(strand_id, session=session)
    if strand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strand not found",
        )
    return StrandResponse(
        strand_id=strand.strand_id,
        organization_id=strand.organization_id,
        created_by=strand.created_by,
        name=strand.name,
        description=strand.description,
        create_time=strand.create_time,
        update_time=strand.update_time,
    )


def _build_strand_with_objectives_response(strand_id: StrandID, session: Session) -> StrandWithObjectivesResponse:
    """Build a strand response with objectives."""
    strand = strand_storage.get(strand_id, session=session)
    if strand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strand not found",
        )

    objectives_in_strand = strand_storage.get_objectives_in_strand(strand_id, session=session)

    return StrandWithObjectivesResponse(
        strand_id=strand.strand_id,
        organization_id=strand.organization_id,
        created_by=strand.created_by,
        name=strand.name,
        description=strand.description,
        create_time=strand.create_time,
        update_time=strand.update_time,
        objectives=[
            ObjectiveInStrandResponse(
                strand_id=ois.strand_id,
                objective_id=ois.objective_id,
                position=ois.position,
            )
            for ois in objectives_in_strand
        ],
    )


@router.post("", operation_id="create_strand", status_code=status.HTTP_201_CREATED)
@di.inject
def create_strand(
    request: StrandCreateRequest,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> StrandResponse:
    """Create a new strand.

    Only educators can create strands.
    """
    strand = strand_storage.create(
        {
            "organization_id": auth.organization_id,
            "created_by": auth.user.user_id,
            "name": request.name,
            "description": request.description,
        },
        session=session,
    )

    session.commit()
    return _build_strand_response(strand.strand_id, session)


@router.get("", operation_id="list_strands")
@di.inject
def list_strands(
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> StrandListResponse:
    """List strands for the educator's organization.

    Only educators can list strands.
    """
    strands = strand_storage.find(
        organization_id=auth.organization_id,
        session=session,
    )

    strand_responses = [
        StrandResponse(
            strand_id=s.strand_id,
            organization_id=s.organization_id,
            created_by=s.created_by,
            name=s.name,
            description=s.description,
            create_time=s.create_time,
            update_time=s.update_time,
        )
        for s in strands
    ]

    return StrandListResponse(
        strands=strand_responses,
        total=len(strand_responses),
    )


@router.get("/{strand_id}", operation_id="get_strand")
@di.inject
def get_strand(
    strand_id: StrandID,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> StrandWithObjectivesResponse:
    """Get strand details with ordered objectives.

    Only educators can view strand details.
    """
    strand = strand_storage.get(strand_id, session=session)
    if strand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strand not found",
        )

    # Verify organization access
    if strand.organization_id != auth.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access strands from other organizations",
        )

    return _build_strand_with_objectives_response(strand_id, session)


@router.put("/{strand_id}", operation_id="update_strand")
@di.inject
def update_strand(
    strand_id: StrandID,
    request: StrandUpdateRequest,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> StrandResponse:
    """Update a strand.

    Only educators can update strands.
    """
    strand = strand_storage.get(strand_id, session=session)
    if strand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strand not found",
        )

    # Verify organization access
    if strand.organization_id != auth.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update strands from other organizations",
        )

    # For now, we'll update directly since we don't have an update function
    # This should be added to the storage layer
    stmt = select(strands_table).where(strands_table.strand_id == strand_id)
    strand_row = session.execute(stmt).scalar_one_or_none()
    if strand_row:
        if request.name is not None:
            strand_row.name = request.name
        if request.description is not None:
            strand_row.description = request.description
        session.flush()

    session.commit()
    return _build_strand_response(strand_id, session)


@router.post(
    "/{strand_id}/objectives",
    operation_id="add_objective_to_strand",
    status_code=status.HTTP_201_CREATED,
)
@di.inject
def add_objective_to_strand(
    strand_id: StrandID,
    request: ObjectiveInStrandRequest,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> ObjectiveInStrandResponse:
    """Add an objective to a strand at a specific position.

    Only educators can add objectives to strands.
    """
    strand = strand_storage.get(strand_id, session=session)
    if strand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strand not found",
        )

    # Verify organization access
    if strand.organization_id != auth.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify strands from other organizations",
        )

    # Verify objective exists and belongs to same organization
    objective = obj_storage.get(request.objective_id, session=session)
    if objective is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Objective not found",
        )
    if objective.organization_id != auth.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot add objectives from other organizations",
        )

    ois = strand_storage.add_objective_to_strand(
        {
            "strand_id": strand_id,
            "objective_id": request.objective_id,
            "position": request.position,
        },
        session=session,
    )

    session.commit()

    return ObjectiveInStrandResponse(
        strand_id=ois.strand_id,
        objective_id=ois.objective_id,
        position=ois.position,
    )


@router.put("/{strand_id}/objectives", operation_id="reorder_objectives")
@di.inject
def reorder_objectives(
    strand_id: StrandID,
    request: ReorderObjectivesRequest,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> StrandWithObjectivesResponse:
    """Reorder objectives in a strand.

    The objective_ids list should contain all objective IDs in the desired order.
    Only educators can reorder objectives.
    """
    strand = strand_storage.get(strand_id, session=session)
    if strand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strand not found",
        )

    # Verify organization access
    if strand.organization_id != auth.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify strands from other organizations",
        )

    # Update positions
    for position, objective_id in enumerate(request.objective_ids):
        stmt = (
            update(objectives_in_strands)
            .where(objectives_in_strands.strand_id == strand_id)
            .where(objectives_in_strands.objective_id == objective_id)
            .values(position=position)
        )
        session.execute(stmt)

    session.commit()

    return _build_strand_with_objectives_response(strand_id, session)


@router.post(
    "/{strand_id}/objectives/{objective_id}/dependencies",
    operation_id="add_objective_dependency",
    status_code=status.HTTP_201_CREATED,
)
@di.inject
def add_objective_dependency(
    strand_id: StrandID,
    objective_id: ObjectiveID,
    request: ObjectiveDependencyRequest,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> ObjectiveDependencyResponse:
    """Add a dependency between objectives in a strand.

    The objective depends on the specified prerequisite objective.
    Only educators can add dependencies.
    """
    strand = strand_storage.get(strand_id, session=session)
    if strand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strand not found",
        )

    # Verify organization access
    if strand.organization_id != auth.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify strands from other organizations",
        )

    # Verify both objectives exist
    objective = obj_storage.get(objective_id, session=session)
    if objective is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Objective not found",
        )

    depends_on = obj_storage.get(request.depends_on_objective_id, session=session)
    if depends_on is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prerequisite objective not found",
        )

    dep = strand_storage.add_dependency(
        {
            "objective_id": objective_id,
            "depends_on_objective_id": request.depends_on_objective_id,
            "dependency_type": request.dependency_type,
        },
        session=session,
    )

    session.commit()

    return ObjectiveDependencyResponse(
        objective_id=dep.objective_id,
        depends_on_objective_id=dep.depends_on_objective_id,
        dependency_type=dep.dependency_type,
    )


@router.get(
    "/{strand_id}/objectives/{objective_id}/dependencies",
    operation_id="get_objective_dependencies",
)
@di.inject
def get_objective_dependencies(
    strand_id: StrandID,
    objective_id: ObjectiveID,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> list[ObjectiveDependencyResponse]:
    """Get dependencies for an objective.

    Only educators can view dependencies.
    """
    strand = strand_storage.get(strand_id, session=session)
    if strand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strand not found",
        )

    # Verify organization access
    if strand.organization_id != auth.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access strands from other organizations",
        )

    dependencies = strand_storage.get_dependencies(objective_id, session=session)

    return [
        ObjectiveDependencyResponse(
            objective_id=d.objective_id,
            depends_on_objective_id=d.depends_on_objective_id,
            dependency_type=d.dependency_type,
        )
        for d in dependencies
    ]
