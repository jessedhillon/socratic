"""View models for strand management."""

from __future__ import annotations

import datetime

import pydantic as p

from socratic.model import DependencyType, ObjectiveID, OrganizationID, StrandID, UserID


class StrandCreateRequest(p.BaseModel):
    """Request to create a new strand."""

    name: str
    description: str | None = None


class StrandUpdateRequest(p.BaseModel):
    """Request to update a strand."""

    name: str | None = None
    description: str | None = None


class StrandResponse(p.BaseModel):
    """Strand details response."""

    strand_id: StrandID
    organization_id: OrganizationID
    created_by: UserID
    name: str
    description: str | None = None
    create_time: datetime.datetime
    update_time: datetime.datetime | None = None


class StrandListResponse(p.BaseModel):
    """List of strands response."""

    strands: list[StrandResponse]
    total: int


class ObjectiveInStrandRequest(p.BaseModel):
    """Request to add an objective to a strand."""

    objective_id: ObjectiveID
    position: int


class ObjectiveInStrandResponse(p.BaseModel):
    """Objective position in strand."""

    strand_id: StrandID
    objective_id: ObjectiveID
    position: int


class ReorderObjectivesRequest(p.BaseModel):
    """Request to reorder objectives in a strand."""

    objective_ids: list[ObjectiveID]


class ObjectiveDependencyRequest(p.BaseModel):
    """Request to add a dependency between objectives."""

    depends_on_objective_id: ObjectiveID
    dependency_type: DependencyType = DependencyType.Hard


class ObjectiveDependencyResponse(p.BaseModel):
    """Dependency between objectives."""

    objective_id: ObjectiveID
    depends_on_objective_id: ObjectiveID
    dependency_type: DependencyType


class StrandWithObjectivesResponse(p.BaseModel):
    """Strand with ordered objectives."""

    strand_id: StrandID
    organization_id: OrganizationID
    created_by: UserID
    name: str
    description: str | None = None
    create_time: datetime.datetime
    update_time: datetime.datetime | None = None
    objectives: list[ObjectiveInStrandResponse] = []
