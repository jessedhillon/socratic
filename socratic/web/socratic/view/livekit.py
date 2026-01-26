"""View models for LiveKit real-time voice interface."""

from __future__ import annotations

from datetime import datetime

import pydantic as p

from socratic.model import AttemptID


class LiveKitRoomTokenResponse(p.BaseModel):
    """Response with LiveKit room access credentials."""

    attempt_id: AttemptID
    room_name: str
    token: str
    url: str


class LiveKitRoomInfoResponse(p.BaseModel):
    """Response with LiveKit room information."""

    room_name: str
    num_participants: int
    created_at: int  # Unix timestamp


class EgressRecordingResponse(p.BaseModel):
    """Response with egress recording information."""

    egress_id: str
    room_name: str
    status: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    file_url: str | None = None
    error: str | None = None


class StartRecordingRequest(p.BaseModel):
    """Request to start recording an assessment room."""

    # Room name is derived from attempt_id, so no additional fields needed
    pass


class StartRecordingResponse(p.BaseModel):
    """Response after starting a recording."""

    egress_id: str
    room_name: str
    status: str


class StopRecordingResponse(p.BaseModel):
    """Response after stopping a recording."""

    egress_id: str
    status: str
    file_url: str | None = None
