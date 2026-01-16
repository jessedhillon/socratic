import datetime
import decimal
import enum

from .base import BaseModel
from .id import AttemptID, TranscriptSegmentID, WordTimingID


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


class WordTiming(BaseModel):
    """Word-level timing data for transcript synchronization with video."""

    word_timing_id: WordTimingID
    segment_id: TranscriptSegmentID

    word: str
    start_offset_ms: int  # Milliseconds from segment start_time
    end_offset_ms: int  # Milliseconds from segment start_time
    confidence: decimal.Decimal | None = None


class TranscriptSegmentWithTimings(BaseModel):
    """Transcript segment with word-level timing data for video synchronization."""

    segment_id: TranscriptSegmentID
    attempt_id: AttemptID

    utterance_type: UtteranceType
    content: str
    start_time: datetime.datetime
    end_time: datetime.datetime | None = None

    confidence: decimal.Decimal | None = None
    prompt_index: int | None = None

    word_timings: list[WordTiming] = []
