"""LiveKit room management for assessments.

Functions for creating and managing LiveKit rooms with assessment context metadata.
"""

from __future__ import annotations

import json
import typing as t

import pydantic as p
from livekit import api as livekit_api  # pyright: ignore [reportMissingTypeStubs]

from socratic.core import di
from socratic.core.config.vendor import LiveKitSettings
from socratic.core.provider import LoggingProvider
from socratic.model import AttemptID


class AssessmentRoomMetadata(t.TypedDict):
    """Room metadata for assessment context."""

    attempt_id: str
    objective_id: str
    objective_title: str
    objective_description: str
    initial_prompts: list[str]
    rubric_criteria: list[dict[str, t.Any]]
    scope_boundaries: str | None
    time_expectation_minutes: int | None
    challenge_prompts: list[str] | None
    extension_policy: str


class RoomInfo(t.TypedDict):
    """Information about a created/existing room."""

    name: str
    sid: str
    num_participants: int
    created_at: int


class RoomError(Exception):
    """Error during room operation."""

    pass


@di.inject
async def create_assessment_room(
    attempt_id: AttemptID,
    metadata: AssessmentRoomMetadata,
    *,
    logging: LoggingProvider = di.Provide["logging"],
    livekit_config: LiveKitSettings = di.Provide["config.vendor.livekit", di.as_(LiveKitSettings)],
    livekit_api_key: p.Secret[str] = di.Provide["secrets.livekit.api_key"],
    livekit_api_secret: p.Secret[str] = di.Provide["secrets.livekit.api_secret"],
    livekit_wss_url: p.Secret[p.WebsocketUrl] = di.Provide["secrets.livekit.wss_url"],
) -> RoomInfo:
    """Create a LiveKit room for an assessment with context metadata.

    The room metadata contains the assessment context needed by the agent:
    - attempt_id, objective info, prompts, rubric, etc.

    The agent server reads this metadata when joining the room.

    Args:
        attempt_id: The assessment attempt ID.
        metadata: Assessment context to store in room metadata.

    Returns:
        RoomInfo with the room details.

    Raises:
        RoomError: If room creation fails.
    """
    logger = logging.get_logger()

    # Build the LiveKit API URL (convert ws:// to http://)
    wss_url = str(livekit_wss_url.get_secret_value())
    api_url = wss_url.replace("ws://", "http://").replace("wss://", "https://")

    lkapi = livekit_api.LiveKitAPI(
        url=api_url,
        api_key=livekit_api_key.get_secret_value(),
        api_secret=livekit_api_secret.get_secret_value(),
    )

    try:
        # Generate room name from attempt ID
        room_name = f"{livekit_config.room_prefix}-{attempt_id}"

        # Serialize metadata as JSON
        metadata_json = json.dumps(metadata)

        # Create the room with metadata and agent dispatch
        room = await lkapi.room.create_room(
            livekit_api.CreateRoomRequest(
                name=room_name,
                metadata=metadata_json,
                # Enable empty timeout so room persists until explicitly deleted
                empty_timeout=300,  # 5 minutes
                # Dispatch the assessment agent to this room
                agents=[
                    livekit_api.RoomAgentDispatch(
                        agent_name=livekit_config.agent_name,
                    ),
                ],
            )
        )

        return RoomInfo(
            name=room.name,
            sid=room.sid,
            num_participants=room.num_participants,
            created_at=room.creation_time,
        )

    except Exception as e:
        logger.exception(f"Failed to create LiveKit room for attempt {attempt_id}")
        raise RoomError("Failed to create assessment room") from e
    finally:
        await lkapi.aclose()


@di.inject
async def delete_room(
    room_name: str,
    *,
    livekit_api_key: p.Secret[str] = di.Provide["secrets.livekit.api_key"],
    livekit_api_secret: p.Secret[str] = di.Provide["secrets.livekit.api_secret"],
    livekit_wss_url: p.Secret[p.WebsocketUrl] = di.Provide["secrets.livekit.wss_url"],
) -> bool:
    """Delete a LiveKit room.

    Args:
        room_name: The room name to delete.

    Returns:
        True if deleted, False if room didn't exist.
    """
    wss_url = str(livekit_wss_url.get_secret_value())
    api_url = wss_url.replace("ws://", "http://").replace("wss://", "https://")

    lkapi = livekit_api.LiveKitAPI(
        url=api_url,
        api_key=livekit_api_key.get_secret_value(),
        api_secret=livekit_api_secret.get_secret_value(),
    )

    try:
        await lkapi.room.delete_room(livekit_api.DeleteRoomRequest(room=room_name))
        return True
    except Exception:
        return False
    finally:
        await lkapi.aclose()


@di.inject
async def get_room(
    room_name: str,
    *,
    livekit_api_key: p.Secret[str] = di.Provide["secrets.livekit.api_key"],
    livekit_api_secret: p.Secret[str] = di.Provide["secrets.livekit.api_secret"],
    livekit_wss_url: p.Secret[p.WebsocketUrl] = di.Provide["secrets.livekit.wss_url"],
) -> RoomInfo | None:
    """Get information about a LiveKit room.

    Args:
        room_name: The room name to look up.

    Returns:
        RoomInfo if found, None otherwise.
    """
    wss_url = str(livekit_wss_url.get_secret_value())
    api_url = wss_url.replace("ws://", "http://").replace("wss://", "https://")

    lkapi = livekit_api.LiveKitAPI(
        url=api_url,
        api_key=livekit_api_key.get_secret_value(),
        api_secret=livekit_api_secret.get_secret_value(),
    )

    try:
        response = await lkapi.room.list_rooms(livekit_api.ListRoomsRequest(names=[room_name]))
        if response.rooms:
            room = response.rooms[0]
            return RoomInfo(
                name=room.name,
                sid=room.sid,
                num_participants=room.num_participants,
                created_at=room.creation_time,
            )
        return None
    except Exception:
        return None
    finally:
        await lkapi.aclose()
