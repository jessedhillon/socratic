"""Speech-to-text transcription service using OpenAI Whisper API."""

from __future__ import annotations

import io
import typing as t
from dataclasses import dataclass

from openai import AsyncOpenAI
from pydantic import SecretStr

# Maximum file size for Whisper API (25MB)
MaxFileSizeBytes = 25 * 1024 * 1024

# Supported audio formats
SupportedFormats = {
    "audio/webm",
    "audio/mp3",
    "audio/mp4",
    "audio/mpeg",
    "audio/mpga",
    "audio/m4a",
    "audio/wav",
    "audio/ogg",
    "video/webm",  # MediaRecorder may use video/webm for audio+video
}


@dataclass
class TranscriptionResult:
    """Result from transcription."""

    text: str
    duration: float | None = None
    language: str | None = None


class TranscriptionError(Exception):
    """Error during transcription."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


class TranscriptionService:
    """Service for transcribing audio using OpenAI Whisper API."""

    def __init__(self, api_key: SecretStr) -> None:
        self._client = AsyncOpenAI(api_key=api_key.get_secret_value())

    async def transcribe(
        self,
        audio_data: bytes,
        *,
        filename: str = "audio.webm",
        content_type: str = "audio/webm",
        language: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe audio data to text.

        Args:
            audio_data: Raw audio bytes
            filename: Original filename (used for format detection)
            content_type: MIME type of the audio
            language: Optional ISO language code to hint to Whisper

        Returns:
            TranscriptionResult with text and optional metadata

        Raises:
            TranscriptionError: If validation fails or API call fails
        """
        # Validate file size
        if len(audio_data) > MaxFileSizeBytes:
            raise TranscriptionError(
                f"File size {len(audio_data)} exceeds maximum {MaxFileSizeBytes} bytes",
                code="file_too_large",
            )

        # Validate content type (strip codec info like "video/webm;codecs=vp9,opus" -> "video/webm")
        base_content_type = content_type.split(";")[0].strip()
        if base_content_type not in SupportedFormats:
            raise TranscriptionError(
                f"Unsupported audio format: {content_type}",
                code="unsupported_format",
            )

        # Call Whisper API
        try:
            # Create a file-like object from bytes
            audio_file = io.BytesIO(audio_data)
            audio_file.name = filename

            if language is not None:
                response = await self._client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                    response_format="verbose_json",
                )
            else:
                response = await self._client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                )

            # verbose_json format returns additional fields as a dict
            # but the SDK returns a Transcription object with .text
            # Use model_dump to access all fields
            response_dict: dict[str, t.Any] = response.model_dump()
            return TranscriptionResult(
                text=str(response_dict.get("text", "")),
                duration=t.cast(float | None, response_dict.get("duration")),
                language=t.cast(str | None, response_dict.get("language")),
            )

        except Exception as e:
            raise TranscriptionError(
                f"Transcription failed: {e!s}",
                code="api_error",
            ) from e
