"""LiveKit agent server for Socratic assessments."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
import typing as t
from types import FrameType

import pydantic as p
from livekit import agents  # pyright: ignore [reportMissingTypeStubs]
from livekit.agents import AgentSession, JobContext  # pyright: ignore [reportMissingTypeStubs]
from livekit.plugins import deepgram, elevenlabs, openai, silero  # pyright: ignore [reportMissingTypeStubs]

from socratic.core import BootConfiguration, di, SocraticContainer

from . import agent as _agent_module
from .agent import create_assessment_agent_from_room_metadata

logger = logging.getLogger(__name__)

handled_signals = (signal.SIGINT, signal.SIGTERM)


@di.inject
async def _handle_session(
    ctx: JobContext,  # pyright: ignore [reportUnknownParameterType]
    *,
    deepgram_api_key: p.Secret[str] = di.Provide["secrets.llm.deepgram.api_key"],  # noqa: B008
    elevenlabs_api_key: p.Secret[str] = di.Provide["secrets.llm.elevenlabs.api_key"],  # noqa: B008
    openai_api_key: p.Secret[str] = di.Provide["secrets.llm.openai.secret_key"],  # noqa: B008
    stt_model: str = di.Provide["config.vendor.livekit.stt_model"],  # noqa: B008
    tts_model: str = di.Provide["config.vendor.livekit.tts_model"],  # noqa: B008
    tts_voice: str = di.Provide["config.vendor.livekit.tts_voice"],  # noqa: B008
) -> None:
    """Handle a LiveKit session with injected dependencies."""
    # Connect to the room first so metadata is available
    await ctx.connect()  # pyright: ignore [reportUnknownMemberType]

    # Create the Socratic assessment agent from room metadata
    try:
        agent = create_assessment_agent_from_room_metadata(
            room=ctx.room,  # pyright: ignore [reportUnknownMemberType, reportUnknownArgumentType]
        )
    except ValueError as e:
        logger.error(f"Failed to create agent: {e}")
        await ctx.room.disconnect()  # pyright: ignore [reportUnknownMemberType]
        return

    # Configure STT provider with API key passed directly
    dg_key = deepgram_api_key.get_secret_value()
    if stt_model.startswith("deepgram/"):
        stt_provider = deepgram.STT(model=stt_model.split("/", 1)[1], api_key=dg_key)  # pyright: ignore [reportUnknownMemberType]
    else:
        stt_provider = deepgram.STT(api_key=dg_key)  # pyright: ignore [reportUnknownMemberType]

    # Configure TTS provider with API key passed directly
    oai_key = openai_api_key.get_secret_value()
    if tts_model.startswith("openai/"):
        tts_provider = openai.TTS(model=tts_model.split("/", 1)[1], voice=tts_voice, api_key=oai_key)  # pyright: ignore [reportUnknownMemberType]
    elif tts_model.startswith("elevenlabs/"):
        tts_provider = elevenlabs.TTS(
            model=tts_model.split("/", 1)[1], voice_id=tts_voice, api_key=elevenlabs_api_key.get_secret_value()
        )  # pyright: ignore [reportUnknownMemberType]
    elif tts_model.startswith("deepgram/"):
        tts_provider = deepgram.TTS(model=tts_model.split("/", 1)[1], api_key=dg_key)  # pyright: ignore [reportUnknownMemberType]
    else:
        tts_provider = openai.TTS(voice=tts_voice, api_key=oai_key)  # pyright: ignore [reportUnknownMemberType]

    # Create the agent session with STT/TTS pipeline
    # An LLM is required for generate_reply() to pass the null-check;
    # actual generation is handled by the agent's llm_node() override.
    #
    # Endpointing delay is set high because learners pause to think during
    # assessments — a 0.5s silence is rarely end-of-turn, more often a
    # breath or thought gap.
    session = AgentSession(  # pyright: ignore [reportUnknownVariableType]
        stt=stt_provider,
        tts=tts_provider,
        vad=silero.VAD.load(),  # pyright: ignore [reportUnknownMemberType]
        llm=openai.LLM(api_key=oai_key),  # pyright: ignore [reportUnknownMemberType]
        min_endpointing_delay=1.5,
    )

    # Start the session with our custom agent
    await session.start(  # pyright: ignore [reportUnknownMemberType]
        room=ctx.room,  # pyright: ignore [reportUnknownMemberType, reportUnknownArgumentType]
        agent=agent,
    )

    # Generate the initial orientation message
    logger.info("Generating orientation message")
    await session.generate_reply(  # pyright: ignore [reportUnknownMemberType]
        instructions="Begin the assessment.",
    )

    logger.info(f"Assessment session started for attempt {agent.attempt_id}")


async def assessment_session(ctx: JobContext) -> None:  # pyright: ignore [reportUnknownParameterType]
    """Handle a LiveKit session for a Socratic assessment.

    This is a module-level function (required for multiprocessing pickling).
    It bootstraps the DI container from __Socratic_BOOT environment variable,
    wires this module, then delegates to the injected handler.
    """
    logger.info(f"Starting assessment session in room {ctx.room.name}")  # pyright: ignore [reportUnknownMemberType]

    # Bootstrap container from serialized boot config (set by parent process)
    boot_json = os.environ.get("__Socratic_BOOT")
    if not boot_json:
        logger.error("__Socratic_BOOT environment variable not set")
        await ctx.room.disconnect()  # pyright: ignore [reportUnknownMemberType]
        return

    try:
        boot_cf = BootConfiguration.model_validate_json(boot_json)
        container = SocraticContainer()
        SocraticContainer.boot(container, **dict(boot_cf))
        container.wire(modules=[__name__, _agent_module])
    except Exception:
        logger.exception("Failed to bootstrap DI container in worker subprocess")
        await ctx.room.disconnect()  # pyright: ignore [reportUnknownMemberType]
        return

    try:
        await _handle_session(ctx)
    except Exception:
        logger.exception("Unhandled error in assessment session")
        await ctx.room.disconnect()  # pyright: ignore [reportUnknownMemberType]


class _ExitServer(Exception):
    """Signal to exit the server event loop."""


def _create_signal_handler() -> t.Callable[[int, FrameType | None], None]:
    """Create a signal handler that raises _ExitServer on first signal."""
    exit_triggered = False

    def handler(sig: int, frame: FrameType | None) -> None:
        nonlocal exit_triggered
        if not exit_triggered:
            exit_triggered = True
            raise _ExitServer()

    return handler


async def _run_server(server: agents.AgentServer, devmode: bool) -> None:  # pyright: ignore [reportUnknownParameterType]
    """Run the agent server (internal async implementation)."""
    try:
        await server.run(devmode=devmode)  # pyright: ignore [reportUnknownMemberType]
    except Exception:
        logger.exception("agent server failed")


def run_agent_server(
    *,
    livekit_wss_url: str,
    livekit_api_key: str,
    livekit_api_secret: str,
    agent_name: str = "socratic-assessment",
    devmode: bool = False,
) -> None:
    """Run the LiveKit agent server.

    This is our own runner that replaces agents.cli.run_app(), avoiding
    sys.argv manipulation and env var pollution.

    Args:
        livekit_wss_url: LiveKit WebSocket URL.
        livekit_api_key: LiveKit API key.
        livekit_api_secret: LiveKit API secret.
        agent_name: Name to register with LiveKit for dispatch routing.
        devmode: Run in development mode with hot reload.
    """
    # Create server with LiveKit credentials passed directly
    server = agents.AgentServer(  # pyright: ignore [reportUnknownMemberType]
        ws_url=livekit_wss_url,
        api_key=livekit_api_key,
        api_secret=livekit_api_secret,
    )
    server.rtc_session(agent_name=agent_name)(assessment_session)  # pyright: ignore [reportUnknownMemberType]

    # Set up signal handling
    handler = _create_signal_handler()
    for sig in handled_signals:
        signal.signal(sig, handler)

    # Run the event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.slow_callback_duration = 0.1  # 100ms

    try:
        main_task = loop.create_task(_run_server(server, devmode), name="agent_server_main")
        try:
            loop.run_until_complete(main_task)
        except _ExitServer:
            pass

        # Graceful shutdown
        try:
            if not devmode:
                loop.run_until_complete(server.drain())  # pyright: ignore [reportUnknownMemberType]
            loop.run_until_complete(server.aclose())  # pyright: ignore [reportUnknownMemberType]
        except _ExitServer:
            logger.warning("forcing exit")
            os._exit(1)
    finally:
        with contextlib.suppress(_ExitServer):
            try:
                tasks = asyncio.all_tasks(loop)
                for task in tasks:
                    task.cancel()
                loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            finally:
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.run_until_complete(loop.shutdown_default_executor())
                loop.close()
