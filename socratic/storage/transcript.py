from __future__ import annotations

import datetime
import decimal
import typing as t

from sqlalchemy import select

from socratic.core import di
from socratic.model import AttemptID, TranscriptSegment, TranscriptSegmentID, UtteranceType

from . import Session
from .table import transcript_segments


def get(
    key: TranscriptSegmentID, session: Session = di.Provide["storage.persistent.session"]
) -> TranscriptSegment | None:
    stmt = select(transcript_segments.__table__).where(transcript_segments.segment_id == key)
    row = session.execute(stmt).mappings().one_or_none()
    return TranscriptSegment(**row) if row else None


def find(
    *,
    attempt_id: AttemptID | None = None,
    utterance_type: UtteranceType | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[TranscriptSegment, ...]:
    stmt = select(transcript_segments.__table__).order_by(transcript_segments.start_time)
    if attempt_id is not None:
        stmt = stmt.where(transcript_segments.attempt_id == attempt_id)
    if utterance_type is not None:
        stmt = stmt.where(transcript_segments.utterance_type == utterance_type.value)
    rows = session.execute(stmt).mappings().all()
    return tuple(TranscriptSegment(**row) for row in rows)


def create(
    params: TranscriptSegmentCreateParams, session: Session = di.Provide["storage.persistent.session"]
) -> TranscriptSegment:
    segment = transcript_segments(
        segment_id=TranscriptSegmentID(),
        attempt_id=params["attempt_id"],
        utterance_type=params["utterance_type"].value,
        content=params["content"],
        start_time=params["start_time"],
        end_time=params.get("end_time"),
        confidence=params.get("confidence"),
        prompt_index=params.get("prompt_index"),
    )
    session.add(segment)
    session.flush()
    return get(segment.segment_id, session=session)  # type: ignore


class TranscriptSegmentCreateParams(t.TypedDict, total=False):
    attempt_id: t.Required[AttemptID]
    utterance_type: t.Required[UtteranceType]
    content: t.Required[str]
    start_time: t.Required[datetime.datetime]
    end_time: datetime.datetime | None
    confidence: decimal.Decimal | None
    prompt_index: int | None
