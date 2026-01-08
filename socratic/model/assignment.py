import datetime
import enum

from .base import BaseModel, WithTimestamps
from .id import AssignmentID, ObjectiveID, OrganizationID, UserID


class RetakePolicy(enum.Enum):
    Immediate = "immediate"
    Delayed = "delayed"
    ManualApproval = "manual_approval"
    None_ = "none"


class Assignment(BaseModel, WithTimestamps):
    assignment_id: AssignmentID
    organization_id: OrganizationID
    objective_id: ObjectiveID
    assigned_by: UserID
    assigned_to: UserID

    available_from: datetime.datetime | None = None
    available_until: datetime.datetime | None = None
    max_attempts: int = 1
    retake_policy: RetakePolicy = RetakePolicy.None_
    retake_delay_hours: int | None = None
