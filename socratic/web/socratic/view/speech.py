"""View models for speech synthesis."""

from __future__ import annotations

import pydantic as p

from socratic.llm import SpeechFormat, Voice


class SpeechRequest(p.BaseModel):
    """Request to synthesize speech from text."""

    text: str = p.Field(..., min_length=1, max_length=4096, description="Text to convert to speech")
    voice: Voice = p.Field(default=Voice.NOVA, description="Voice to use for synthesis")
    format: SpeechFormat = p.Field(default=SpeechFormat.MP3, description="Output audio format")
    speed: float = p.Field(default=1.0, ge=0.25, le=4.0, description="Speech speed (0.25-4.0)")
