"""Speech-to-text transcription service interface and implementations."""

from __future__ import annotations

import io
import typing as t
from abc import abstractmethod

import pydantic as p
from openai import AsyncOpenAI


class TranscriptionResult(p.BaseModel):
    """Result from transcription."""

    text: str
    duration: float | None = None
    language: str | None = None


class TranscriptionError(Exception):
    """Error during transcription."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


class TranscriptionService(t.Protocol):
    """Protocol for speech-to-text transcription services.

    Implementations can use different backends (OpenAI Whisper, Google Speech, etc.)
    while exposing a consistent interface.
    """

    @property
    @abstractmethod
    def max_file_size(self) -> int:
        """Maximum file size in bytes that this service accepts."""
        ...

    @abstractmethod
    def supports_format(self, content_type: str) -> bool:
        """Check if a content type is supported.

        Args:
            content_type: MIME type, optionally with codec suffix
                (e.g., "audio/webm" or "video/webm;codecs=vp9,opus")

        Returns:
            True if the format is supported, False otherwise.
        """
        ...

    @abstractmethod
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
            language: Optional ISO language code hint

        Returns:
            TranscriptionResult with text and optional metadata

        Raises:
            TranscriptionError: If validation fails or transcription fails
        """
        ...


class WhisperTranscriptionService(object):
    """Transcription service using OpenAI Whisper API."""

    # Whisper API limits
    MaxFileSizeBytes = 25 * 1024 * 1024  # 25MB

    SupportedFormats = frozenset({
        "audio/webm",
        "audio/mp3",
        "audio/mp4",
        "audio/mpeg",
        "audio/mpga",
        "audio/m4a",
        "audio/wav",
        "audio/ogg",
        "video/webm",  # MediaRecorder may use video/webm for audio+video
    })

    def __init__(self, api_key: p.SecretStr) -> None:
        self._client = AsyncOpenAI(api_key=api_key.get_secret_value())

    @property
    def max_file_size(self) -> int:
        """Maximum file size in bytes (25MB for Whisper)."""
        return self.MaxFileSizeBytes

    def supports_format(self, content_type: str) -> bool:
        """Check if a content type is supported by Whisper.

        Handles codec suffixes like "video/webm;codecs=vp9,opus".
        """
        base_content_type = content_type.split(";")[0].strip()
        return base_content_type in self.SupportedFormats

    async def transcribe(
        self,
        audio_data: bytes,
        *,
        filename: str = "audio.webm",
        content_type: str = "audio/webm",
        language: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe audio data to text using OpenAI Whisper.

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
        if len(audio_data) > self.max_file_size:
            raise TranscriptionError(
                f"File size {len(audio_data)} exceeds maximum {self.max_file_size} bytes",
                code="file_too_large",
            )

        # Validate content type
        if not self.supports_format(content_type):
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
