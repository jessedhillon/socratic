import enum

from .base import BaseModel, WithTimestamps
from .id import ObjectiveID, OrganizationID, StrandID, UserID


class DependencyType(enum.Enum):
    Hard = "hard"
    Soft = "soft"


class Strand(BaseModel, WithTimestamps):
    strand_id: StrandID
    organization_id: OrganizationID
    created_by: UserID

    name: str
    description: str | None = None


class ObjectiveInStrand(BaseModel):
    strand_id: StrandID
    objective_id: ObjectiveID
    position: int


class ObjectiveDependency(BaseModel):
    objective_id: ObjectiveID
    depends_on_objective_id: ObjectiveID
    dependency_type: DependencyType = DependencyType.Hard
