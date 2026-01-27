"""LiveKit Egress service for recording assessments.

Provides functions for starting, stopping, and managing room composite recordings
using the LiveKit Egress API. Recordings can be output to S3-compatible storage.
"""

from __future__ import annotations

import typing as t
from datetime import datetime

import pydantic as p
from livekit import api as livekit_api  # pyright: ignore [reportMissingTypeStubs]

from socratic.core import di
from socratic.core.config.vendor import LiveKitSettings


class EgressRecording(p.BaseModel):
    """Information about an egress recording."""

    model_config = p.ConfigDict(frozen=True)

    egress_id: str
    room_name: str
    status: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    file_url: str | None = None
    error: str | None = None


class EgressError(Exception):
    """Error during egress operation."""

    def __init__(self, message: str, egress_id: str | None = None) -> None:
        super().__init__(message)
        self.egress_id = egress_id


def _get_egress_status_string(status: int) -> str:
    """Convert LiveKit egress status enum to string."""
    status_map = {
        0: "starting",
        1: "active",
        2: "ending",
        3: "complete",
        4: "failed",
        5: "aborted",
        6: "limit_reached",
    }
    return status_map.get(status, "unknown")


def _egress_info_to_recording(info: t.Any) -> EgressRecording:
    """Convert LiveKit EgressInfo to EgressRecording model."""
    # Extract file URL from file results if available
    file_url: str | None = None

    # Check repeated file_results field first (newer API)
    if hasattr(info, "file_results") and info.file_results:
        for file_result in info.file_results:
            if hasattr(file_result, "location") and file_result.location:
                file_url = file_result.location
                break

    # Fall back to singular file field (deprecated but still populated by LiveKit)
    if file_url is None and hasattr(info, "file") and info.file:
        if hasattr(info.file, "location") and info.file.location:
            file_url = info.file.location

    # Extract timestamps
    started_at: datetime | None = None
    ended_at: datetime | None = None
    if hasattr(info, "started_at") and info.started_at:
        started_at = datetime.fromtimestamp(info.started_at / 1_000_000_000)  # nanoseconds to seconds
    if hasattr(info, "ended_at") and info.ended_at:
        ended_at = datetime.fromtimestamp(info.ended_at / 1_000_000_000)

    # Extract error message if failed
    error: str | None = None
    if hasattr(info, "error") and info.error:
        error = info.error

    return EgressRecording(
        egress_id=info.egress_id,
        room_name=info.room_name,
        status=_get_egress_status_string(info.status),
        started_at=started_at,
        ended_at=ended_at,
        file_url=file_url,
        error=error,
    )


@di.inject
async def start_room_recording(
    room_name: str,
    *,
    livekit_config: LiveKitSettings = di.Provide["config.vendor.livekit", di.as_(LiveKitSettings)],
    livekit_api_key: p.Secret[str] = di.Provide["secrets.livekit.api_key"],
    livekit_api_secret: p.Secret[str] = di.Provide["secrets.livekit.api_secret"],
    livekit_wss_url: p.Secret[p.WebsocketUrl] = di.Provide["secrets.livekit.wss_url"],
    s3_access_key: p.Secret[str] | None = di.Provide["secrets.livekit.egress.s3_access_key"],
    s3_secret_key: p.Secret[str] | None = di.Provide["secrets.livekit.egress.s3_secret_key"],
) -> EgressRecording:
    """Start a room composite recording for an assessment room.

    Args:
        room_name: The LiveKit room name to record.

    Returns:
        EgressRecording with the egress ID and status.

    Raises:
        EgressError: If recording fails to start.
    """
    egress_config = livekit_config.egress

    # Build the LiveKit API URL (convert ws:// to http://)
    wss_url = str(livekit_wss_url.get_secret_value())
    api_url = wss_url.replace("ws://", "http://").replace("wss://", "https://")

    lkapi = livekit_api.LiveKitAPI(
        url=api_url,
        api_key=livekit_api_key.get_secret_value(),
        api_secret=livekit_api_secret.get_secret_value(),
    )

    try:
        # Build file output configuration
        file_type = (
            livekit_api.EncodedFileType.MP4
            if egress_config.file_type.lower() == "mp4"
            else livekit_api.EncodedFileType.OGG
        )

        # Generate filepath with room name and timestamp
        filepath = f"{egress_config.s3_prefix}{{room_name}}-{{time}}.{egress_config.file_type}"

        # Build output configuration based on whether S3 is configured
        file_output: livekit_api.EncodedFileOutput
        if egress_config.s3_bucket and s3_access_key and s3_secret_key:
            # S3 output
            s3_upload = livekit_api.S3Upload(
                access_key=s3_access_key.get_secret_value(),
                secret=s3_secret_key.get_secret_value(),
                bucket=egress_config.s3_bucket,
                region=egress_config.s3_region or "",
                endpoint=egress_config.s3_endpoint or "",
                force_path_style=egress_config.s3_force_path_style,
            )
            file_output = livekit_api.EncodedFileOutput(
                file_type=file_type,
                filepath=filepath,
                s3=s3_upload,
            )
        else:
            # Local file output (for development)
            # LiveKit Egress will save to the configured egress directory
            file_output = livekit_api.EncodedFileOutput(
                file_type=file_type,
                filepath=filepath,
            )

        # Start the room composite egress
        egress_info = await lkapi.egress.start_room_composite_egress(
            livekit_api.RoomCompositeEgressRequest(
                room_name=room_name,
                layout=egress_config.layout,
                file_outputs=[file_output],
            )
        )

        return _egress_info_to_recording(egress_info)

    except Exception as e:
        raise EgressError(f"Failed to start recording: {e}") from e
    finally:
        await lkapi.aclose()


@di.inject
async def stop_recording(
    egress_id: str,
    *,
    livekit_api_key: p.Secret[str] = di.Provide["secrets.livekit.api_key"],
    livekit_api_secret: p.Secret[str] = di.Provide["secrets.livekit.api_secret"],
    livekit_wss_url: p.Secret[p.WebsocketUrl] = di.Provide["secrets.livekit.wss_url"],
) -> EgressRecording:
    """Stop an active egress recording.

    Args:
        egress_id: The egress ID to stop.

    Returns:
        EgressRecording with the final status and file URL.

    Raises:
        EgressError: If stopping the recording fails.
    """
    wss_url = str(livekit_wss_url.get_secret_value())
    api_url = wss_url.replace("ws://", "http://").replace("wss://", "https://")

    lkapi = livekit_api.LiveKitAPI(
        url=api_url,
        api_key=livekit_api_key.get_secret_value(),
        api_secret=livekit_api_secret.get_secret_value(),
    )

    try:
        egress_info = await lkapi.egress.stop_egress(livekit_api.StopEgressRequest(egress_id=egress_id))
        return _egress_info_to_recording(egress_info)

    except Exception as e:
        raise EgressError(f"Failed to stop recording: {e}", egress_id=egress_id) from e
    finally:
        await lkapi.aclose()


@di.inject
async def list_recordings(
    room_name: str | None = None,
    *,
    active_only: bool = False,
    livekit_api_key: p.Secret[str] = di.Provide["secrets.livekit.api_key"],
    livekit_api_secret: p.Secret[str] = di.Provide["secrets.livekit.api_secret"],
    livekit_wss_url: p.Secret[p.WebsocketUrl] = di.Provide["secrets.livekit.wss_url"],
) -> tuple[EgressRecording, ...]:
    """List egress recordings.

    Args:
        room_name: Optional room name filter.
        active_only: If True, only return active recordings.

    Returns:
        Tuple of EgressRecording objects.
    """
    wss_url = str(livekit_wss_url.get_secret_value())
    api_url = wss_url.replace("ws://", "http://").replace("wss://", "https://")

    lkapi = livekit_api.LiveKitAPI(
        url=api_url,
        api_key=livekit_api_key.get_secret_value(),
        api_secret=livekit_api_secret.get_secret_value(),
    )

    try:
        response = await lkapi.egress.list_egress(
            livekit_api.ListEgressRequest(
                room_name=room_name or "",
                active=active_only,
            )
        )

        return tuple(_egress_info_to_recording(info) for info in response.items)

    finally:
        await lkapi.aclose()


@di.inject
async def get_recording(
    egress_id: str,
    *,
    livekit_api_key: p.Secret[str] = di.Provide["secrets.livekit.api_key"],
    livekit_api_secret: p.Secret[str] = di.Provide["secrets.livekit.api_secret"],
    livekit_wss_url: p.Secret[p.WebsocketUrl] = di.Provide["secrets.livekit.wss_url"],
) -> EgressRecording | None:
    """Get information about a specific egress recording.

    Args:
        egress_id: The egress ID to look up.

    Returns:
        EgressRecording if found, None otherwise.
    """
    wss_url = str(livekit_wss_url.get_secret_value())
    api_url = wss_url.replace("ws://", "http://").replace("wss://", "https://")

    lkapi = livekit_api.LiveKitAPI(
        url=api_url,
        api_key=livekit_api_key.get_secret_value(),
        api_secret=livekit_api_secret.get_secret_value(),
    )

    try:
        response = await lkapi.egress.list_egress(
            livekit_api.ListEgressRequest(
                egress_id=egress_id,
            )
        )

        if response.items:
            return _egress_info_to_recording(response.items[0])
        return None

    finally:
        await lkapi.aclose()
