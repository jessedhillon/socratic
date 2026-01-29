from __future__ import annotations

import datetime
import decimal
import typing as t

import pydantic as p
import sqlalchemy as sqla

from socratic.core import di
from socratic.model import AttemptID, TranscriptSegment, TranscriptSegmentID, TranscriptSegmentWithTimings, \
    UtteranceType, WordTiming, WordTimingID

from . import AsyncSession, Session
from .table import transcript_segments, word_timings


class WordTimingParams(p.BaseModel):
    """Parameters for creating a word timing entry."""

    model_config = p.ConfigDict(frozen=True)

    word: str
    start_offset_ms: int
    end_offset_ms: int
    confidence: decimal.Decimal | None = None

    def __hash__(self) -> int:
        return hash((self.word, self.start_offset_ms, self.end_offset_ms))


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


async def acreate(
    *,
    attempt_id: AttemptID,
    utterance_type: UtteranceType,
    content: str,
    start_time: datetime.datetime,
    end_time: datetime.datetime | None = None,
    confidence: decimal.Decimal | None = None,
    prompt_index: int | None = None,
    session: AsyncSession,
) -> TranscriptSegment:
    """Create a new transcript segment (async)."""
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
    await session.execute(stmt)
    await session.flush()
    select_stmt = sqla.select(transcript_segments.__table__).where(transcript_segments.segment_id == segment_id)
    row = (await session.execute(select_stmt)).mappings().one()
    return TranscriptSegment(**row)


# Word Timing Functions


def get_word_timing(
    word_timing_id: WordTimingID,
    *,
    session: Session = di.Provide["storage.persistent.session"],
) -> WordTiming | None:
    """Get a word timing entry by ID."""
    stmt = sqla.select(word_timings.__table__).where(word_timings.word_timing_id == word_timing_id)
    row = session.execute(stmt).mappings().one_or_none()
    return WordTiming(**row) if row else None


def find_word_timings(
    *,
    segment_id: TranscriptSegmentID | None = None,
    attempt_id: AttemptID | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[WordTiming, ...]:
    """Find word timings matching criteria.

    If segment_id is provided, returns word timings for that segment.
    If attempt_id is provided, returns all word timings for all segments in that attempt.
    """
    stmt = sqla.select(word_timings.__table__).order_by(word_timings.start_offset_ms)

    if segment_id is not None:
        stmt = stmt.where(word_timings.segment_id == segment_id)
    elif attempt_id is not None:
        # Join with transcript_segments to filter by attempt_id
        stmt = stmt.join(
            transcript_segments,
            word_timings.segment_id == transcript_segments.segment_id,
        ).where(transcript_segments.attempt_id == attempt_id)

    rows = session.execute(stmt).mappings().all()
    return tuple(WordTiming(**row) for row in rows)


def create_word_timings(
    segment_id: TranscriptSegmentID,
    timings: t.Sequence[WordTimingParams],
    *,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[WordTiming, ...]:
    """Create multiple word timing entries for a segment.

    Args:
        segment_id: The transcript segment these timings belong to.
        timings: Sequence of word timing parameters.
        session: Database session.

    Returns:
        Tuple of created WordTiming objects.
    """
    if not timings:
        return ()

    created_ids: list[WordTimingID] = []

    for timing in timings:
        word_timing_id = WordTimingID()
        stmt = sqla.insert(word_timings).values(
            word_timing_id=word_timing_id,
            segment_id=segment_id,
            word=timing.word,
            start_offset_ms=timing.start_offset_ms,
            end_offset_ms=timing.end_offset_ms,
            confidence=timing.confidence,
        )
        session.execute(stmt)
        created_ids.append(word_timing_id)

    session.flush()

    # Fetch all created timings
    return tuple(t.cast(WordTiming, get_word_timing(wid, session=session)) for wid in created_ids)


def find_with_timings(
    *,
    attempt_id: AttemptID,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[TranscriptSegmentWithTimings, ...]:
    """Find transcript segments with their word timings for an attempt.

    Returns segments ordered by start_time, with word_timings populated.
    """
    # Get all segments for the attempt
    segments = find(attempt_id=attempt_id, session=session)

    # Get all word timings for these segments in one query
    segment_ids = [s.segment_id for s in segments]
    if not segment_ids:
        return ()

    stmt = (
        sqla
        .select(word_timings.__table__)
        .where(word_timings.segment_id.in_(segment_ids))
        .order_by(word_timings.start_offset_ms)
    )
    timing_rows = session.execute(stmt).mappings().all()

    # Group timings by segment_id
    timings_by_segment: dict[TranscriptSegmentID, list[WordTiming]] = {}
    for row in timing_rows:
        wt = WordTiming(**row)
        if wt.segment_id not in timings_by_segment:
            timings_by_segment[wt.segment_id] = []
        timings_by_segment[wt.segment_id].append(wt)

    # Build TranscriptSegmentWithTimings objects
    return tuple(
        TranscriptSegmentWithTimings(
            segment_id=s.segment_id,
            attempt_id=s.attempt_id,
            utterance_type=s.utterance_type,
            content=s.content,
            start_time=s.start_time,
            end_time=s.end_time,
            confidence=s.confidence,
            prompt_index=s.prompt_index,
            word_timings=timings_by_segment.get(s.segment_id, []),
        )
        for s in segments
    )
