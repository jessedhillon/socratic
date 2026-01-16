"""View models for transcription API."""

from __future__ import annotations

import pydantic as p


class TranscriptionResponse(p.BaseModel):
    """Response from transcription API."""

    text: str
    duration: float | None = None
    language: str | None = None


class TranscriptionErrorResponse(p.BaseModel):
    """Error response from transcription API."""

    error: str
    code: str
