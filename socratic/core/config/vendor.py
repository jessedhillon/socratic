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


class LiveKitSettings(BaseSettings):
    room_prefix: str = "assessment"
    stt_model: str = "deepgram/nova-3"
    tts_model: str = "openai/tts-1"
    tts_voice: str = "alloy"
