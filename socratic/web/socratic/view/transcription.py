"""View models for transcription API."""

from __future__ import annotations

import pydantic as p


class WordTimingResponse(p.BaseModel):
    """Word-level timing data from transcription."""

    word: str
    start: float = p.Field(description="Start time in seconds")
    end: float = p.Field(description="End time in seconds")


class TranscriptionResponse(p.BaseModel):
    """Response from transcription API."""

    text: str
    duration: float | None = None
    language: str | None = None
    words: list[WordTimingResponse] | None = p.Field(
        default=None,
        description="Word-level timing data (only present if include_word_timings=true)",
    )


class TranscriptionErrorResponse(p.BaseModel):
    """Error response from transcription API."""

    error: str
    code: str
