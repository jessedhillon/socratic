"""View models for LiveKit real-time voice interface."""

from __future__ import annotations

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
