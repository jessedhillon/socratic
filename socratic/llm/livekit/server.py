"""LiveKit agent server for Socratic assessments."""

from __future__ import annotations

import logging
import typing as t

import jinja2
from langchain_core.language_models import BaseChatModel
from livekit import agents  # pyright: ignore [reportMissingTypeStubs]
from livekit.agents import AgentSession  # pyright: ignore [reportMissingTypeStubs]
from livekit.plugins import deepgram, openai, silero  # pyright: ignore [reportMissingTypeStubs]

from .agent import create_assessment_agent_from_room_metadata

logger = logging.getLogger(__name__)


def create_agent_server(
    model: BaseChatModel,
    env: jinja2.Environment,
    *,
    stt_model: str = "deepgram/nova-3",
    tts_model: str = "openai/tts-1",
    tts_voice: str = "alloy",
) -> agents.AgentServer:  # pyright: ignore [reportUnknownVariableType, reportReturnType]
    """Create a LiveKit agent server for Socratic assessments.

    Args:
        model: LangChain chat model for the assessment agent.
        env: Jinja2 environment for rendering prompt templates.
        stt_model: Speech-to-text model identifier (default: deepgram/nova-3).
        tts_model: Text-to-speech model identifier (default: openai/tts-1).
        tts_voice: Voice to use for TTS (default: alloy).

    Returns:
        Configured AgentServer ready to handle LiveKit sessions.
    """
    server = agents.AgentServer()  # pyright: ignore [reportUnknownMemberType]

    @server.rtc_session()  # pyright: ignore [reportUnknownMemberType]
    async def assessment_session(ctx: agents.JobContext) -> None:  # pyright: ignore [reportUnknownParameterType, reportUnusedFunction]
        """Handle a LiveKit session for a Socratic assessment.

        The room metadata must contain the assessment context (attempt_id,
        objective info, prompts, rubric, etc.) as JSON.
        """
        logger.info(f"Starting assessment session in room {ctx.room.name}")  # pyright: ignore [reportUnknownMemberType]

        # Create the Socratic assessment agent from room metadata
        try:
            agent = create_assessment_agent_from_room_metadata(
                room=ctx.room,  # pyright: ignore [reportUnknownMemberType, reportUnknownArgumentType]
                model=model,
                env=env,
            )
        except ValueError as e:
            logger.error(f"Failed to create agent: {e}")
            # Disconnect gracefully if we can't create the agent
            await ctx.room.disconnect()  # pyright: ignore [reportUnknownMemberType]
            return

        # Configure STT provider
        if stt_model.startswith("deepgram/"):
            stt_provider = deepgram.STT(model=stt_model.split("/", 1)[1])  # pyright: ignore [reportUnknownMemberType]
        else:
            # Default to Deepgram
            stt_provider = deepgram.STT()  # pyright: ignore [reportUnknownMemberType]

        # Configure TTS provider
        if tts_model.startswith("openai/"):
            tts_provider = openai.TTS(model=tts_model.split("/", 1)[1], voice=tts_voice)  # pyright: ignore [reportUnknownMemberType]
        elif tts_model.startswith("deepgram/"):
            tts_provider = deepgram.TTS(model=tts_model.split("/", 1)[1])  # pyright: ignore [reportUnknownMemberType]
        else:
            # Default to OpenAI TTS
            tts_provider = openai.TTS(voice=tts_voice)  # pyright: ignore [reportUnknownMemberType]

        # Create the agent session with STT/TTS pipeline
        session = AgentSession(  # pyright: ignore [reportUnknownVariableType]
            stt=stt_provider,
            tts=tts_provider,
            vad=silero.VAD.load(),  # pyright: ignore [reportUnknownMemberType]
        )

        # Start the session with our custom agent
        await session.start(  # pyright: ignore [reportUnknownMemberType]
            room=ctx.room,  # pyright: ignore [reportUnknownMemberType, reportUnknownArgumentType]
            agent=agent,
        )

        # Generate the initial orientation message
        # The agent's llm_node will handle the actual content generation
        logger.info("Generating orientation message")
        await session.generate_reply(  # pyright: ignore [reportUnknownMemberType]
            instructions="Begin the assessment.",
        )

        logger.info(f"Assessment session started for attempt {agent.attempt_id}")

    return server


def run_agent_server(
    model: BaseChatModel,
    env: jinja2.Environment,
    **kwargs: t.Any,
) -> None:
    """Run the LiveKit agent server.

    This is a blocking call that runs the agent server's event loop.

    Args:
        model: LangChain chat model for the assessment agent.
        env: Jinja2 environment for rendering prompt templates.
        **kwargs: Additional arguments passed to create_agent_server.
    """
    server = create_agent_server(model, env, **kwargs)
    agents.cli.run_app(server)  # pyright: ignore [reportUnknownMemberType]
