"""Speech-to-text transcription service interface and implementations."""

from __future__ import annotations

import io
import typing as t
from abc import abstractmethod

import pydantic as p
from openai import AsyncOpenAI
from openai.types.audio import Transcription


class WordTiming(p.BaseModel):
    """Word-level timing from transcription."""

    word: str
    start: float  # Start time in seconds
    end: float  # End time in seconds


class TranscriptionResult(p.BaseModel):
    """Result from transcription."""

    text: str
    duration: float | None = None
    language: str | None = None
    words: list[WordTiming] | None = None  # Word-level timings (optional)


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
        include_word_timings: bool = False,
    ) -> TranscriptionResult:
        """Transcribe audio data to text.

        Args:
            audio_data: Raw audio bytes
            filename: Original filename (used for format detection)
            content_type: MIME type of the audio
            language: Optional ISO language code hint
            include_word_timings: If True, request word-level timing data

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
        include_word_timings: bool = False,
    ) -> TranscriptionResult:
        """Transcribe audio data to text using OpenAI Whisper.

        Args:
            audio_data: Raw audio bytes
            filename: Original filename (used for format detection)
            content_type: MIME type of the audio
            language: Optional ISO language code to hint to Whisper
            include_word_timings: If True, request word-level timing data

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

            # Build API call arguments
            api_args: dict[str, t.Any] = {
                "model": "whisper-1",
                "file": audio_file,
                "response_format": "verbose_json",
            }

            if language is not None:
                api_args["language"] = language

            if include_word_timings:
                api_args["timestamp_granularities"] = ["word"]

            response = t.cast(
                Transcription,
                await self._client.audio.transcriptions.create(**api_args),
            )

            # verbose_json format returns additional fields as a dict
            # but the SDK returns a Transcription object with .text
            # Use model_dump to access all fields
            response_dict = response.model_dump()

            # Parse word-level timings if requested and available
            words: list[WordTiming] | None = None
            if include_word_timings and "words" in response_dict:
                raw_words = t.cast(list[dict[str, t.Any]], response_dict["words"])
                words = [
                    WordTiming(
                        word=str(w.get("word", "")),
                        start=float(w.get("start", 0.0)),
                        end=float(w.get("end", 0.0)),
                    )
                    for w in raw_words
                ]

            return TranscriptionResult(
                text=str(response_dict.get("text", "")),
                duration=t.cast(float | None, response_dict.get("duration")),
                language=t.cast(str | None, response_dict.get("language")),
                words=words,
            )

        except Exception as e:
            raise TranscriptionError(
                f"Transcription failed: {e!s}",
                code="api_error",
            ) from e
