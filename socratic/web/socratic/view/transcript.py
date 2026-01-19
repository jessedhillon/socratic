"""View models for transcript synchronization."""

from __future__ import annotations

import datetime

import pydantic as p


class WordTimingResponse(p.BaseModel):
    """Word-level timing data for transcript synchronization."""

    word: str
    start_offset_ms: int = p.Field(description="Start offset in milliseconds from segment start")
    end_offset_ms: int = p.Field(description="End offset in milliseconds from segment start")
    confidence: float | None = p.Field(default=None, description="Confidence score (0-1)")


class SynchronizedSegmentResponse(p.BaseModel):
    """Transcript segment with word-level timing data."""

    segment_id: str
    attempt_id: str
    utterance_type: str = p.Field(description="Who spoke: learner, interviewer, or system")
    content: str
    start_time: datetime.datetime
    end_time: datetime.datetime | None = None
    confidence: float | None = None
    prompt_index: int | None = None
    word_timings: list[WordTimingResponse] = p.Field(default_factory=lambda: list[WordTimingResponse]())


class SynchronizedTranscriptResponse(p.BaseModel):
    """Complete synchronized transcript for an attempt."""

    attempt_id: str
    video_url: str | None = p.Field(default=None, description="URL of the video recording")
    segments: list[SynchronizedSegmentResponse] = p.Field(default_factory=lambda: list[SynchronizedSegmentResponse]())
