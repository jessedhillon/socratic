from __future__ import annotations

import pydantic as p

from .base import BaseSettings


class VendorSettings(BaseSettings):
    google: GoogleSettings
    livekit: LiveKitSettings


class GoogleServiceAccountSettings(BaseSettings):
    project_id: str
    private_key_id: str
    client_id: str
    client_email: p.EmailStr


class GoogleSettings(BaseSettings):
    service_account: GoogleServiceAccountSettings


class LiveKitEgressSettings(BaseSettings):
    """Settings for LiveKit egress recording output."""

    # S3-compatible storage settings
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_endpoint: str | None = None  # For non-AWS S3-compatible providers
    s3_force_path_style: bool = False  # Set to True for MinIO, etc.
    s3_prefix: str = "recordings/"

    # Recording settings
    file_type: str = "mp4"  # mp4 or ogg
    layout: str = "speaker-dark"  # grid-dark, grid-light, speaker-dark, speaker-light


class LiveKitSettings(BaseSettings):
    agent_name: str = "socratic-assessment"
    room_prefix: str = "assessment"
    stt_model: str = "deepgram/nova-3"
    tts_model: str = "openai/tts-1"
    tts_voice: str = "alloy"
    egress: LiveKitEgressSettings = LiveKitEgressSettings()
