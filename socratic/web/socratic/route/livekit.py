"""LiveKit real-time voice API routes."""

from __future__ import annotations

import json
import logging

import pydantic as p
from fastapi import APIRouter, Depends, HTTPException, status
from livekit import api as livekit_api  # pyright: ignore [reportMissingTypeStubs]
from livekit.protocol import room as livekit_room  # pyright: ignore [reportMissingTypeStubs]
from sqlalchemy.orm import Session

from socratic.auth import AuthContext, require_learner
from socratic.core import di
from socratic.core.config.vendor import LiveKitSettings
from socratic.model import AttemptID
from socratic.storage import assignment as assignment_storage
from socratic.storage import attempt as attempt_storage
from socratic.storage import objective as objective_storage
from socratic.storage import rubric as rubric_storage

from ..view.livekit import LiveKitRoomTokenResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/livekit", tags=["livekit"])


@router.post(
    "/rooms/{attempt_id}/token",
    operation_id="get_livekit_room_token",
    response_model=LiveKitRoomTokenResponse,
)
@di.inject
async def get_room_token(
    attempt_id: AttemptID,
    auth: AuthContext = Depends(require_learner),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
    livekit_config: LiveKitSettings = Depends(di.Provide["config.vendor.livekit", di.as_(LiveKitSettings)]),
    livekit_api_key: p.Secret[str] = Depends(di.Provide["secrets.livekit.api_key"]),
    livekit_api_secret: p.Secret[str] = Depends(di.Provide["secrets.livekit.api_secret"]),
    livekit_wss_url: p.Secret[p.WebsocketUrl] = Depends(di.Provide["secrets.livekit.wss_url"]),
    lk_api: livekit_api.LiveKitAPI = Depends(di.Provide["vendor.livekit.api"]),
) -> LiveKitRoomTokenResponse:
    """Generate a LiveKit room token for a learner to join an assessment room.

    Creates the room with assessment metadata (objective, rubric, prompts) so the
    agent can initialize when it joins. The room name is derived from the attempt ID
    with a configured prefix. Only the learner assigned to the attempt can get a token.
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

        # Load assignment, objective, and rubric for room metadata
        assignment = assignment_storage.get(attempt.assignment_id, session=session)
        if assignment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found",
            )

        objective = objective_storage.get(assignment.objective_id, session=session)
        if objective is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Objective not found",
            )

        rubric_criteria = rubric_storage.find(objective_id=objective.objective_id, session=session)

    # Build assessment context metadata for the agent
    serialized_criteria = [
        {
            "criterion_id": str(c.criterion_id),
            "name": c.name,
            "description": c.description,
            "proficiency_levels": [{"grade": pl.grade, "description": pl.description} for pl in c.proficiency_levels],
        }
        for c in rubric_criteria
    ]

    room_metadata = json.dumps({
        "attempt_id": str(attempt.attempt_id),
        "objective_id": str(objective.objective_id),
        "objective_title": objective.title,
        "objective_description": objective.description,
        "initial_prompts": objective.initial_prompts,
        "rubric_criteria": serialized_criteria,
        "scope_boundaries": objective.scope_boundaries,
        "time_expectation_minutes": objective.time_expectation_minutes,
        "challenge_prompts": objective.challenge_prompts,
        "extension_policy": objective.extension_policy.value,
    })

    # Generate room name from attempt ID
    room_name = f"{livekit_config.room_prefix}-{attempt_id}"

    # Create the room with metadata so the agent can read it on join
    await lk_api.room.create_room(  # pyright: ignore [reportUnknownMemberType]
        livekit_room.CreateRoomRequest(name=room_name, metadata=room_metadata),
    )
    logger.info(f"Created LiveKit room {room_name} with assessment metadata")

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
        url=str(livekit_wss_url.get_secret_value()),
    )
