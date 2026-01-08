import datetime
import decimal
import enum

from .base import BaseModel
from .id import AttemptID, TranscriptSegmentID


class UtteranceType(enum.Enum):
    Learner = "learner"
    Interviewer = "interviewer"
    System = "system"


class TranscriptSegment(BaseModel):
    segment_id: TranscriptSegmentID
    attempt_id: AttemptID

    utterance_type: UtteranceType
    content: str
    start_time: datetime.datetime
    end_time: datetime.datetime | None = None

    confidence: decimal.Decimal | None = None
    prompt_index: int | None = None
