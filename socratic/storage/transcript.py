from __future__ import annotations

import datetime
import decimal

import sqlalchemy as sqla

from socratic.core import di
from socratic.model import AttemptID, TranscriptSegment, TranscriptSegmentID, UtteranceType

from . import Session
from .table import transcript_segments


def get(
    segment_id: TranscriptSegmentID,
    *,
    session: Session = di.Provide["storage.persistent.session"],
) -> TranscriptSegment | None:
    """Get a transcript segment by ID."""
    stmt = sqla.select(transcript_segments.__table__).where(transcript_segments.segment_id == segment_id)
    row = session.execute(stmt).mappings().one_or_none()
    return TranscriptSegment(**row) if row else None


def find(
    *,
    attempt_id: AttemptID | None = None,
    utterance_type: UtteranceType | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[TranscriptSegment, ...]:
    """Find transcript segments matching criteria."""
    stmt = sqla.select(transcript_segments.__table__).order_by(transcript_segments.start_time)
    if attempt_id is not None:
        stmt = stmt.where(transcript_segments.attempt_id == attempt_id)
    if utterance_type is not None:
        stmt = stmt.where(transcript_segments.utterance_type == utterance_type.value)
    rows = session.execute(stmt).mappings().all()
    return tuple(TranscriptSegment(**row) for row in rows)


def create(
    *,
    attempt_id: AttemptID,
    utterance_type: UtteranceType,
    content: str,
    start_time: datetime.datetime,
    end_time: datetime.datetime | None = None,
    confidence: decimal.Decimal | None = None,
    prompt_index: int | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> TranscriptSegment:
    """Create a new transcript segment."""
    segment_id = TranscriptSegmentID()
    stmt = sqla.insert(transcript_segments).values(
        segment_id=segment_id,
        attempt_id=attempt_id,
        utterance_type=utterance_type.value,
        content=content,
        start_time=start_time,
        end_time=end_time,
        confidence=confidence,
        prompt_index=prompt_index,
    )
    session.execute(stmt)
    session.flush()
    result = get(segment_id, session=session)
    assert result is not None
    return result
