"""Unit tests for WhisperTranscriptionService."""

from __future__ import annotations

import typing as t

import pytest
from pydantic import SecretStr

from socratic.llm import TranscriptionError, WhisperTranscriptionService


class TestWhisperTranscriptionService(object):
    """Test WhisperTranscriptionService validation and behavior."""

    @pytest.fixture
    async def service(self) -> t.AsyncGenerator[WhisperTranscriptionService]:
        """Create a transcription service with a fake API key.

        The API key doesn't need to be valid for validation tests
        since they fail before making any API calls.
        """
        svc = WhisperTranscriptionService(api_key=SecretStr("fake-api-key"))
        yield svc
        await svc.aclose()

    def test_max_file_size_is_25mb(self) -> None:
        """Whisper API accepts files up to 25MB."""
        svc = WhisperTranscriptionService(api_key=SecretStr("fake-api-key"))
        assert svc.max_file_size == 25 * 1024 * 1024

    def test_supports_format_for_valid_types(self) -> None:
        """supports_format returns True for all Whisper-supported formats."""
        svc = WhisperTranscriptionService(api_key=SecretStr("fake-api-key"))
        for fmt in ["audio/webm", "audio/mp3", "audio/wav", "video/webm"]:
            assert svc.supports_format(fmt) is True

    def test_supports_format_with_codec_suffix(self) -> None:
        """supports_format handles codec suffixes correctly."""
        svc = WhisperTranscriptionService(api_key=SecretStr("fake-api-key"))
        assert svc.supports_format("video/webm;codecs=vp9,opus") is True
        assert svc.supports_format("audio/webm; codecs=opus") is True

    def test_supports_format_for_invalid_types(self) -> None:
        """supports_format returns False for unsupported formats."""
        svc = WhisperTranscriptionService(api_key=SecretStr("fake-api-key"))
        assert svc.supports_format("audio/unknown") is False
        assert svc.supports_format("text/plain") is False

    @pytest.mark.anyio
    async def test_rejects_oversized_file(self, service: WhisperTranscriptionService) -> None:
        """Files exceeding 25MB should be rejected with file_too_large error."""
        # Create data that exceeds the 25MB limit
        large_data = b"x" * (25 * 1024 * 1024 + 1)  # 25MB + 1 byte

        with pytest.raises(TranscriptionError) as exc_info:
            await service.transcribe(large_data, content_type="audio/webm")

        assert exc_info.value.code == "file_too_large"
        assert "exceeds maximum" in str(exc_info.value)

    @pytest.mark.anyio
    async def test_rejects_unsupported_format(self, service: WhisperTranscriptionService) -> None:
        """Unsupported audio formats should be rejected with unsupported_format error."""
        audio_data = b"fake audio data"

        with pytest.raises(TranscriptionError) as exc_info:
            await service.transcribe(audio_data, content_type="audio/unknown")

        assert exc_info.value.code == "unsupported_format"
        assert "Unsupported audio format" in str(exc_info.value)

    @pytest.mark.anyio
    async def test_accepts_content_type_with_codec_suffix(self, service: WhisperTranscriptionService) -> None:
        """Content types with codec suffixes should be accepted.

        Browsers send MIME types like 'video/webm;codecs=vp9,opus' which
        should be accepted since the base type 'video/webm' is supported.

        Note: This test will fail at the API call stage (since we use a fake key),
        but it should NOT fail at the content type validation stage.
        """
        audio_data = b"fake audio data"

        with pytest.raises(TranscriptionError) as exc_info:
            await service.transcribe(audio_data, content_type="video/webm;codecs=vp9,opus")

        # Should fail with api_error (authentication), NOT unsupported_format
        assert exc_info.value.code == "api_error"

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "content_type",
        [
            "audio/webm",
            "audio/mp3",
            "audio/mp4",
            "audio/mpeg",
            "audio/mpga",
            "audio/m4a",
            "audio/wav",
            "audio/ogg",
            "video/webm",
        ],
    )
    async def test_accepts_supported_formats(self, service: WhisperTranscriptionService, content_type: str) -> None:
        """All documented formats should pass validation.

        Note: These tests will fail at the API call stage (since we use a fake key),
        but they should NOT fail at the content type validation stage.
        """
        audio_data = b"fake audio data"

        with pytest.raises(TranscriptionError) as exc_info:
            await service.transcribe(audio_data, content_type=content_type)

        # Should fail with api_error (authentication), NOT unsupported_format
        assert exc_info.value.code == "api_error"

    @pytest.mark.anyio
    async def test_file_at_size_limit_is_accepted(self, service: WhisperTranscriptionService) -> None:
        """Files exactly at the 25MB limit should be accepted."""
        # Create data exactly at the limit
        data_at_limit = b"x" * (25 * 1024 * 1024)  # Exactly 25MB

        with pytest.raises(TranscriptionError) as exc_info:
            await service.transcribe(data_at_limit, content_type="audio/webm")

        # Should fail with api_error (authentication), NOT file_too_large
        assert exc_info.value.code == "api_error"
