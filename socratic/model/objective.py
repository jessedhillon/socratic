import enum

from .base import BaseModel, WithTimestamps
from .id import ObjectiveID, OrganizationID, UserID


class ExtensionPolicy(enum.Enum):
    Allowed = "allowed"
    Disallowed = "disallowed"
    Conditional = "conditional"


class ObjectiveStatus(enum.Enum):
    Draft = "draft"
    Published = "published"
    Archived = "archived"


class Objective(BaseModel, WithTimestamps):
    objective_id: ObjectiveID
    organization_id: OrganizationID
    created_by: UserID

    title: str
    description: str
    scope_boundaries: str | None = None
    time_expectation_minutes: int | None = None

    initial_prompts: list[str] = []
    challenge_prompts: list[str] = []

    extension_policy: ExtensionPolicy = ExtensionPolicy.Disallowed
    status: ObjectiveStatus = ObjectiveStatus.Draft
