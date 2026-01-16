"""Transcription API routes for speech-to-text."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, status, UploadFile

from socratic.auth import AuthContext, require_learner
from socratic.core import di
from socratic.llm import TranscriptionError, TranscriptionService

from ..view.transcription import TranscriptionResponse

router = APIRouter(prefix="/api/transcription", tags=["transcription"])


@router.post("", operation_id="transcribe_audio")
@di.inject
async def transcribe_audio_route(
    file: UploadFile = File(...),
    language: str | None = Form(None),
    auth: AuthContext = Depends(require_learner),
    transcription_service: TranscriptionService = Depends(di.Provide["llm.transcription_service"]),
) -> TranscriptionResponse:
    """Transcribe audio to text using OpenAI Whisper.

    Accepts audio files up to 25MB in common formats (webm, mp3, mp4, wav, etc.).
    Returns the transcribed text along with optional duration and detected language.

    The learner must be authenticated to use this endpoint.
    """
    # Read audio data
    audio_data = await file.read()

    # Get content type (may be None)
    content_type = file.content_type or "audio/webm"

    try:
        result = await transcription_service.transcribe(
            audio_data,
            filename=file.filename or "audio.webm",
            content_type=content_type,
            language=language,
        )

        return TranscriptionResponse(
            text=result.text,
            duration=result.duration,
            language=result.language,
        )

    except TranscriptionError as e:
        if e.code == "file_too_large":
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=str(e),
            ) from None
        elif e.code == "unsupported_format":
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=str(e),
            ) from None
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            ) from e
