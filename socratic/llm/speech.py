"""Text-to-speech service interface and implementations."""

from __future__ import annotations

import typing as t
from abc import abstractmethod
from enum import Enum

import pydantic as p
from openai import AsyncOpenAI


class Voice(str, Enum):
    """Available TTS voices."""

    ALLOY = "alloy"
    ECHO = "echo"
    FABLE = "fable"
    ONYX = "onyx"
    NOVA = "nova"
    SHIMMER = "shimmer"


class SpeechFormat(str, Enum):
    """Supported audio output formats."""

    MP3 = "mp3"
    OPUS = "opus"
    AAC = "aac"
    FLAC = "flac"
    WAV = "wav"
    PCM = "pcm"


# Content type mapping for each format
ContentTypes: dict[SpeechFormat, str] = {
    SpeechFormat.MP3: "audio/mpeg",
    SpeechFormat.OPUS: "audio/opus",
    SpeechFormat.AAC: "audio/aac",
    SpeechFormat.FLAC: "audio/flac",
    SpeechFormat.WAV: "audio/wav",
    SpeechFormat.PCM: "audio/pcm",
}


class SpeechResult(t.NamedTuple):
    """Result of a TTS operation."""

    audio_data: bytes
    content_type: str
    format: SpeechFormat


class SpeechError(Exception):
    """Error during speech synthesis."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


class SpeechService(t.Protocol):
    """Protocol for text-to-speech synthesis services.

    Implementations can use different backends (OpenAI TTS, Google Cloud TTS, etc.)
    while exposing a consistent interface.
    """

    @property
    @abstractmethod
    def max_text_length(self) -> int:
        """Maximum text length in characters that this service accepts."""
        ...

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        *,
        voice: Voice = Voice.NOVA,
        format: SpeechFormat = SpeechFormat.MP3,
        speed: float = 1.0,
    ) -> SpeechResult:
        """Convert text to speech.

        Args:
            text: The text to convert to speech.
            voice: The voice to use for synthesis.
            format: The output audio format.
            speed: The speed of the generated audio (0.25 to 4.0).

        Returns:
            SpeechResult containing the audio data and metadata.

        Raises:
            SpeechError: If validation fails or synthesis fails.
        """
        ...


class OpenAISpeechService(object):
    """Speech synthesis service using OpenAI TTS API."""

    # OpenAI TTS API limits
    MaxTextLength = 4096

    def __init__(self, api_key: p.SecretStr) -> None:
        """Initialize the speech service.

        Args:
            api_key: OpenAI API key.
        """
        self._client = AsyncOpenAI(api_key=api_key.get_secret_value())

    @property
    def max_text_length(self) -> int:
        """Maximum text length in characters (4096 for OpenAI TTS)."""
        return self.MaxTextLength

    async def synthesize(
        self,
        text: str,
        *,
        voice: Voice = Voice.NOVA,
        format: SpeechFormat = SpeechFormat.MP3,
        speed: float = 1.0,
    ) -> SpeechResult:
        """Convert text to speech using OpenAI TTS.

        Args:
            text: The text to convert to speech.
            voice: The voice to use for synthesis.
            format: The output audio format.
            speed: The speed of the generated audio (0.25 to 4.0).

        Returns:
            SpeechResult containing the audio data and metadata.

        Raises:
            SpeechError: If validation fails or API call fails.
        """
        # Validate inputs
        if not text or not text.strip():
            raise SpeechError("Text cannot be empty", code="empty_text")

        if len(text) > self.max_text_length:
            raise SpeechError(
                f"Text length {len(text)} exceeds maximum {self.max_text_length} characters",
                code="text_too_long",
            )

        if not 0.25 <= speed <= 4.0:
            raise SpeechError(
                "Speed must be between 0.25 and 4.0",
                code="invalid_speed",
            )

        try:
            response = await self._client.audio.speech.create(
                model="tts-1",
                voice=voice.value,
                input=text,
                response_format=format.value,
                speed=speed,
            )

            # Read the audio data from the response
            audio_data = response.read()

            return SpeechResult(
                audio_data=audio_data,
                content_type=ContentTypes[format],
                format=format,
            )

        except Exception as e:
            raise SpeechError(
                f"TTS synthesis failed: {e!s}",
                code="api_error",
            ) from e
