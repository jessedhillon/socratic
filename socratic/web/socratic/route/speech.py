"""Speech synthesis routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from socratic.auth import AuthContext, require_learner
from socratic.core import di
from socratic.llm import SpeechService
from socratic.web.socratic.view.speech import SpeechRequest

router = APIRouter(prefix="/speech", tags=["speech"])


@router.post("", operation_id="synthesize_speech")
@di.inject
async def synthesize_speech_route(
    request: SpeechRequest,
    auth: AuthContext = Depends(require_learner),
    speech_service: SpeechService = Depends(di.Provide["llm.speech_service"]),
) -> Response:
    """Synthesize speech from text.

    Returns audio data in the requested format.
    """
    try:
        result = await speech_service.synthesize(
            request.text,
            voice=request.voice,
            format=request.format,
            speed=request.speed,
        )

        return Response(
            content=result.audio_data,
            media_type=result.content_type,
            headers={
                "Content-Disposition": f'inline; filename="speech.{result.format.value}"',
            },
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
