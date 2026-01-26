"""LiveKit real-time voice API routes."""

from __future__ import annotations

import pydantic as p
from fastapi import APIRouter, Depends, HTTPException, status
from livekit import api as livekit_api  # pyright: ignore [reportMissingTypeStubs]
from sqlalchemy.orm import Session

from socratic.auth import AuthContext, require_learner
from socratic.core import di
from socratic.core.config.vendor import LiveKitSettings
from socratic.model import AttemptID
from socratic.storage import attempt as attempt_storage

from ..view.livekit import LiveKitRoomTokenResponse

router = APIRouter(prefix="/api/livekit", tags=["livekit"])


@router.post(
    "/rooms/{attempt_id}/token",
    operation_id="get_livekit_room_token",
    response_model=LiveKitRoomTokenResponse,
)
@di.inject
def get_room_token(
    attempt_id: AttemptID,
    auth: AuthContext = Depends(require_learner),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
    livekit_config: LiveKitSettings = Depends(di.Provide["config.vendor.livekit", di.as_(LiveKitSettings)]),
    livekit_api_key: p.Secret[str] = Depends(di.Provide["secrets.livekit.api_key"]),
    livekit_api_secret: p.Secret[str] = Depends(di.Provide["secrets.livekit.api_secret"]),
) -> LiveKitRoomTokenResponse:
    """Generate a LiveKit room token for a learner to join an assessment room.

    The room name is derived from the attempt ID with a configured prefix.
    Only the learner assigned to the attempt can get a token for that room.
    """
    # Verify the attempt exists and belongs to this learner
    with session.begin():
        attempt = attempt_storage.get(attempt_id=attempt_id, session=session)

    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment attempt not found",
        )

    if attempt.learner_id != auth.user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this assessment",
        )

    # Generate room name from attempt ID
    room_name = f"{livekit_config.room_prefix}-{attempt_id}"

    # Generate access token for the learner
    token = (
        livekit_api
        .AccessToken(
            api_key=livekit_api_key.get_secret_value(),
            api_secret=livekit_api_secret.get_secret_value(),
        )
        .with_identity(str(auth.user.user_id))
        .with_name(auth.user.name)
        .with_grants(
            livekit_api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .to_jwt()
    )

    return LiveKitRoomTokenResponse(
        attempt_id=attempt_id,
        room_name=room_name,
        token=token,
        url=livekit_config.url,
    )
