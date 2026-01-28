"""CLI commands for running LiveKit voice agents."""

from __future__ import annotations

import asyncio
import os

import pydantic as p
from livekit import api as livekit_api  # pyright: ignore [reportMissingTypeStubs]
from livekit.protocol import room as livekit_room  # pyright: ignore [reportMissingTypeStubs]

import socratic.lib.cli as click
import socratic.llm.livekit as livekit
from socratic.core import BootConfiguration, di, LoggingProvider


@click.group()
def agent() -> None:
    """Commands for running voice agents."""
    ...


@agent.command(name="serve")
@click.option("--dev", is_flag=True, default=False, help="Run in development mode")
@di.inject
def serve(
    dev: bool,
    boot_cf: BootConfiguration = di.Provide["_boot_config"],  # noqa: B008
    logging_provider: LoggingProvider = di.Provide["logging"],  # noqa: B008
    livekit_wss_url: p.Secret[p.WebsocketUrl] = di.Provide["secrets.livekit.wss_url"],  # noqa: B008
    livekit_api_key: p.Secret[str] = di.Provide["secrets.livekit.api_key"],  # noqa: B008
    livekit_api_secret: p.Secret[str] = di.Provide["secrets.livekit.api_secret"],  # noqa: B008
    agent_name: str = di.Provide["config.vendor.livekit.agent_name"],  # noqa: B008
) -> None:
    """Run the LiveKit voice agent server.

    This server handles real-time voice assessments via LiveKit.
    Room metadata must contain the assessment context (attempt_id,
    objective info, prompts, rubric) as JSON.
    """
    logger = logging_provider.get_logger()

    # Set boot config for worker processes (includes paths to load secrets)
    os.environ["__Socratic_BOOT"] = boot_cf.model_dump_json()

    logger.info("Starting LiveKit agent server")
    livekit.run_agent_server(
        livekit_wss_url=str(livekit_wss_url.get_secret_value()),
        livekit_api_key=livekit_api_key.get_secret_value(),
        livekit_api_secret=livekit_api_secret.get_secret_value(),
        agent_name=agent_name,
        devmode=dev,
    )


@agent.command(name="delete-room")
@click.argument("room_name", required=False)
@click.option("--all", "delete_all", is_flag=True, default=False, help="Delete all rooms")
@di.inject
def delete_room(
    room_name: str | None,
    delete_all: bool,
    logging_provider: LoggingProvider = di.Provide["logging"],  # noqa: B008
    livekit_wss_url: p.Secret[p.WebsocketUrl] = di.Provide["secrets.livekit.wss_url"],  # noqa: B008
    livekit_api_key: p.Secret[str] = di.Provide["secrets.livekit.api_key"],  # noqa: B008
    livekit_api_secret: p.Secret[str] = di.Provide["secrets.livekit.api_secret"],  # noqa: B008
) -> None:
    """Delete a LiveKit room by name, or all rooms with --all."""
    if not room_name and not delete_all:
        raise click.UsageError("Provide a ROOM_NAME or use --all to delete all rooms.")

    logger = logging_provider.get_logger()

    async def _delete() -> None:
        lk = livekit_api.LiveKitAPI(
            url=str(livekit_wss_url.get_secret_value()),
            api_key=livekit_api_key.get_secret_value(),
            api_secret=livekit_api_secret.get_secret_value(),
        )
        try:
            if delete_all:
                resp = await lk.room.list_rooms(  # pyright: ignore [reportUnknownMemberType]
                    livekit_room.ListRoomsRequest(),
                )
                rooms = resp.rooms  # pyright: ignore [reportUnknownMemberType]
                if not rooms:
                    click.echo("No rooms found.")
                    return
                for r in rooms:
                    await lk.room.delete_room(  # pyright: ignore [reportUnknownMemberType]
                        livekit_room.DeleteRoomRequest(room=r.name),
                    )
                    logger.info(f"Deleted room: {r.name} (sid={r.sid})")
                click.echo(f"Deleted {len(rooms)} room(s).")
            else:
                assert room_name is not None
                await lk.room.delete_room(  # pyright: ignore [reportUnknownMemberType]
                    livekit_room.DeleteRoomRequest(room=room_name),
                )
                logger.info(f"Deleted room: {room_name}")
                click.echo(f"Deleted room: {room_name}")
        finally:
            await lk.aclose()  # pyright: ignore [reportUnknownMemberType]

    asyncio.run(_delete())
