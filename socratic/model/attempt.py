import datetime
import decimal
import enum

from .base import BaseModel, WithCtime
from .id import AssignmentID, AttemptID, UserID


class Grade(enum.Enum):
    S = "S"
    A = "A"
    C = "C"
    F = "F"


class AttemptStatus(enum.Enum):
    NotStarted = "not_started"
    InProgress = "in_progress"
    Completed = "completed"
    Evaluated = "evaluated"
    Reviewed = "reviewed"


class AssessmentAttempt(BaseModel, WithCtime):
    attempt_id: AttemptID
    assignment_id: AssignmentID
    learner_id: UserID

    status: AttemptStatus = AttemptStatus.NotStarted
    started_at: datetime.datetime | None = None
    completed_at: datetime.datetime | None = None

    grade: Grade | None = None
    confidence_score: decimal.Decimal | None = None

    audio_url: str | None = None
    video_url: str | None = None
