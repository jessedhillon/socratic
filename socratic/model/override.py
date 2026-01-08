from .attempt import Grade
from .base import BaseModel, WithCtime
from .id import AttemptID, OverrideID, UserID


class EducatorOverride(BaseModel, WithCtime):
    override_id: OverrideID
    attempt_id: AttemptID
    educator_id: UserID

    original_grade: Grade | None = None
    new_grade: Grade
    reason: str
    feedback: str | None = None
