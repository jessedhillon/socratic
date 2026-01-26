"""LiveKit real-time voice API routes."""

from __future__ import annotations

import datetime
import json
import logging
import typing as t

import pydantic as p
from fastapi import APIRouter, Depends, HTTPException, status
from livekit import api as livekit_api  # pyright: ignore [reportMissingTypeStubs]
from livekit.protocol import room as livekit_room  # pyright: ignore [reportMissingTypeStubs]
from sqlalchemy.orm import Session

from socratic.auth import AuthContext, require_educator, require_learner
from socratic.core import di
from socratic.core.config.vendor import LiveKitSettings
from socratic.livekit import egress as egress_service
from socratic.livekit import room as room_service
from socratic.livekit.egress import EgressError
from socratic.livekit.room import RoomError
from socratic.model import AssignmentID, AttemptID, AttemptStatus
from socratic.storage import assignment as assignment_storage
from socratic.storage import attempt as attempt_storage
from socratic.storage import objective as objective_storage
from socratic.storage import rubric as rubric_storage

from ..view.livekit import EgressRecordingResponse, LiveKitRoomTokenResponse, StartLiveKitAssessmentResponse, \
    StartRecordingResponse, StopRecordingResponse

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


@router.post(
    "/assessments/{assignment_id}/start",
    operation_id="start_livekit_assessment",
    response_model=StartLiveKitAssessmentResponse,
)
@di.inject
async def start_assessment(
    assignment_id: str,
    auth: AuthContext = Depends(require_learner),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
    livekit_config: LiveKitSettings = di.Provide["config.vendor.livekit", di.as_(LiveKitSettings)],
    livekit_api_key: str = di.Provide["secrets.livekit.api_key"],
    livekit_api_secret: str = di.Provide["secrets.livekit.api_secret"],
) -> StartLiveKitAssessmentResponse:
    """Start a new LiveKit-based assessment.

    Creates an assessment attempt and a LiveKit room with assessment context
    in the metadata. The agent server will automatically join and begin
    the assessment when the learner connects.

    Returns everything the frontend needs to connect to the room.
    """
    aid = AssignmentID(assignment_id)

    with session.begin():
        # Validate assignment exists and belongs to the learner
        assignment = assignment_storage.get(aid, session=session)
        if assignment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found",
            )

        if assignment.assigned_to != auth.user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This assignment is not yours",
            )

        # Check availability window
        now = datetime.datetime.now(datetime.UTC)
        if assignment.available_from and now < assignment.available_from:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assignment is not yet available",
            )
        if assignment.available_until and now > assignment.available_until:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assignment is no longer available",
            )

        # Check attempt limits
        existing_attempts = attempt_storage.find(assignment_id=aid, session=session)
        if len(existing_attempts) >= assignment.max_attempts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum attempts reached",
            )

        # Get objective and rubric data
        objective = objective_storage.get(assignment.objective_id, session=session)
        if objective is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Objective not found",
            )

        rubric_criteria = rubric_storage.find(objective_id=objective.objective_id, session=session)
        serialized_criteria: list[dict[str, t.Any]] = [
            {
                "criterion_id": str(c.criterion_id),
                "name": c.name,
                "description": c.description,
                "proficiency_levels": [
                    {"grade": pl.grade, "description": pl.description} for pl in c.proficiency_levels
                ],
            }
            for c in rubric_criteria
        ]

        # Create new attempt record
        attempt = attempt_storage.create(
            assignment_id=aid,
            learner_id=auth.user.user_id,
            status=AttemptStatus.InProgress,
            session=session,
        )

        attempt_id = attempt.attempt_id
        objective_id = str(objective.objective_id)
        objective_title = objective.title
        objective_description = objective.description
        initial_prompts = list(objective.initial_prompts)
        scope_boundaries = objective.scope_boundaries
        time_expectation_minutes = objective.time_expectation_minutes
        challenge_prompts = list(objective.challenge_prompts) if objective.challenge_prompts else None
        extension_policy = objective.extension_policy.value

    # Create LiveKit room with assessment metadata
    room_metadata = room_service.AssessmentRoomMetadata(
        attempt_id=str(attempt_id),
        objective_id=objective_id,
        objective_title=objective_title,
        objective_description=objective_description,
        initial_prompts=initial_prompts,
        rubric_criteria=serialized_criteria,
        scope_boundaries=scope_boundaries,
        time_expectation_minutes=time_expectation_minutes,
        challenge_prompts=challenge_prompts,
        extension_policy=extension_policy,
    )

    try:
        room_info = await room_service.create_assessment_room(attempt_id, room_metadata)
    except RoomError as e:
        # Rollback the attempt if room creation fails
        with session.begin():
            # Delete the attempt we just created
            # (In practice, might want to mark it as failed instead)
            pass  # TODO: Add attempt deletion or status update
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create assessment room: {e}",
        ) from e

    # Generate access token for the learner
    token = (
        livekit_api
        .AccessToken(
            api_key=livekit_api_key,
            api_secret=livekit_api_secret,
        )
        .with_identity(str(auth.user.user_id))
        .with_name(auth.user.name)
        .with_grants(
            livekit_api.VideoGrants(
                room_join=True,
                room=room_info["name"],
                can_publish=True,
                can_subscribe=True,
            )
        )
        .to_jwt()
    )

    return StartLiveKitAssessmentResponse(
        attempt_id=attempt_id,
        assignment_id=assignment_id,
        objective_id=objective_id,
        objective_title=objective_title,
        room_name=room_info["name"],
        token=token,
        url=livekit_config.url,
    )


@router.post(
    "/rooms/{attempt_id}/recording",
    operation_id="start_room_recording",
    response_model=StartRecordingResponse,
)
@di.inject
async def start_recording(
    attempt_id: AttemptID,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
    livekit_config: LiveKitSettings = di.Provide["config.vendor.livekit", di.as_(LiveKitSettings)],
) -> StartRecordingResponse:
    """Start recording an assessment room.

    Only instructors can start recordings. The recording will capture
    all audio and video from the room as a composite.
    """
    # Verify the attempt exists
    with session.begin():
        attempt = attempt_storage.get(attempt_id=attempt_id, session=session)

    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment attempt not found",
        )

    # Generate room name from attempt ID
    room_name = f"{livekit_config.room_prefix}-{attempt_id}"

    try:
        recording = await egress_service.start_room_recording(room_name)
        return StartRecordingResponse(
            egress_id=recording.egress_id,
            room_name=recording.room_name,
            status=recording.status,
        )
    except EgressError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e


@router.delete(
    "/rooms/{attempt_id}/recording/{egress_id}",
    operation_id="stop_room_recording",
    response_model=StopRecordingResponse,
)
@di.inject
async def stop_recording(
    attempt_id: AttemptID,
    egress_id: str,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> StopRecordingResponse:
    """Stop an active recording.

    Stops the specified egress recording and returns the final status
    with the file URL once processing is complete.
    """
    # Verify the attempt exists
    with session.begin():
        attempt = attempt_storage.get(attempt_id=attempt_id, session=session)

    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment attempt not found",
        )

    try:
        recording = await egress_service.stop_recording(egress_id)

        # Update the attempt with the recording URL if available
        if recording.file_url:
            with session.begin():
                attempt_storage.update(
                    attempt_id,
                    video_url=recording.file_url,
                    session=session,
                )

        return StopRecordingResponse(
            egress_id=recording.egress_id,
            status=recording.status,
            file_url=recording.file_url,
        )
    except EgressError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e


@router.get(
    "/rooms/{attempt_id}/recording/{egress_id}",
    operation_id="get_room_recording",
    response_model=EgressRecordingResponse,
)
@di.inject
async def get_recording(
    attempt_id: AttemptID,
    egress_id: str,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> EgressRecordingResponse:
    """Get the status of a recording.

    Returns detailed information about the egress recording including
    its current status, timestamps, and file URL if complete.
    """
    # Verify the attempt exists
    with session.begin():
        attempt = attempt_storage.get(attempt_id=attempt_id, session=session)

    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment attempt not found",
        )

    recording = await egress_service.get_recording(egress_id)

    if recording is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found",
        )

    return EgressRecordingResponse(
        egress_id=recording.egress_id,
        room_name=recording.room_name,
        status=recording.status,
        started_at=recording.started_at,
        ended_at=recording.ended_at,
        file_url=recording.file_url,
        error=recording.error,
    )


@router.get(
    "/rooms/{attempt_id}/recordings",
    operation_id="list_room_recordings",
    response_model=list[EgressRecordingResponse],
)
@di.inject
async def list_recordings(
    attempt_id: AttemptID,
    active_only: bool = False,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
    livekit_config: LiveKitSettings = di.Provide["config.vendor.livekit", di.as_(LiveKitSettings)],
) -> list[EgressRecordingResponse]:
    """List all recordings for an assessment room.

    Returns a list of all egress recordings associated with the
    specified assessment attempt.
    """
    # Verify the attempt exists
    with session.begin():
        attempt = attempt_storage.get(attempt_id=attempt_id, session=session)

    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment attempt not found",
        )

    # Generate room name from attempt ID
    room_name = f"{livekit_config.room_prefix}-{attempt_id}"

    recordings = await egress_service.list_recordings(room_name, active_only=active_only)

    return [
        EgressRecordingResponse(
            egress_id=r.egress_id,
            room_name=r.room_name,
            status=r.status,
            started_at=r.started_at,
            ended_at=r.ended_at,
            file_url=r.file_url,
            error=r.error,
        )
        for r in recordings
    ]
