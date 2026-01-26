"""CLI commands for running LiveKit voice agents."""

from __future__ import annotations

import jinja2
from langchain_core.language_models import BaseChatModel

import socratic.lib.cli as click
from socratic.core import di
from socratic.core.config import LoggingSettings


@click.group()
def agent() -> None:
    """Commands for running voice agents."""
    ...


@agent.command(name="serve")
@click.option("--stt-model", default="deepgram/nova-3", help="Speech-to-text model")
@click.option("--tts-model", default="openai/tts-1", help="Text-to-speech model")
@click.option("--tts-voice", default="alloy", help="TTS voice")
@di.inject
def serve(
    stt_model: str,
    tts_model: str,
    tts_voice: str,
    logging_cf: LoggingSettings = di.Provide["config.logging", di.as_(LoggingSettings)],  # noqa: B008
    model: BaseChatModel = di.Provide["llm.assessment.model"],  # noqa: B008
    env: jinja2.Environment = di.Provide["template.assessment.env"],  # noqa: B008
) -> None:
    """Run the LiveKit voice agent server.

    This server handles real-time voice assessments via LiveKit.
    Room metadata must contain the assessment context (attempt_id,
    objective info, prompts, rubric) as JSON.

    Environment variables required:
    - LIVEKIT_URL: LiveKit server URL
    - LIVEKIT_API_KEY: LiveKit API key
    - LIVEKIT_API_SECRET: LiveKit API secret
    - DEEPGRAM_API_KEY: Deepgram API key (for STT)
    - OPENAI_API_KEY: OpenAI API key (for TTS)
    """
    # Configure logging
    import logging.config

    from socratic.llm.livekit import run_agent_server

    logging.config.dictConfig(logging_cf.model_dump())

    click.echo(f"Starting LiveKit agent server (STT: {stt_model}, TTS: {tts_model})")
    run_agent_server(
        model=model,
        env=env,
        stt_model=stt_model,
        tts_model=tts_model,
        tts_voice=tts_voice,
    )
