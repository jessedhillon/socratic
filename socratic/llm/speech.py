"""Text-to-speech service using OpenAI TTS API."""

from __future__ import annotations

import typing as t
from enum import Enum

from openai import AsyncOpenAI
from pydantic import SecretStr


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
CONTENT_TYPES: dict[SpeechFormat, str] = {
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


class SpeechService(object):
    """Service for converting text to speech using OpenAI TTS API."""

    # Maximum text length for TTS (OpenAI limit is 4096 characters)
    MAX_TEXT_LENGTH = 4096

    def __init__(self, api_key: SecretStr) -> None:
        """Initialize the speech service.

        Args:
            api_key: OpenAI API key.
        """
        self._client = AsyncOpenAI(api_key=api_key.get_secret_value())

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
            ValueError: If text is empty or too long, or speed is out of range.
            RuntimeError: If the TTS API call fails.
        """
        # Validate inputs
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        if len(text) > self.MAX_TEXT_LENGTH:
            raise ValueError(f"Text exceeds maximum length of {self.MAX_TEXT_LENGTH} characters")

        if not 0.25 <= speed <= 4.0:
            raise ValueError("Speed must be between 0.25 and 4.0")

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
                content_type=CONTENT_TYPES[format],
                format=format,
            )

        except Exception as e:
            raise RuntimeError(f"TTS synthesis failed: {e}") from e
