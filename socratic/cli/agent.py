"""CLI commands for running LiveKit voice agents."""

from __future__ import annotations

import os

import pydantic as p

import socratic.lib.cli as click
from socratic.core import BootConfiguration, di
from socratic.core.config import LoggingSettings


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
    logging_cf: LoggingSettings = di.Provide["config.logging", di.as_(LoggingSettings)],  # noqa: B008
    livekit_wss_url: p.Secret[p.WebsocketUrl] = di.Provide["secrets.livekit.wss_url"],  # noqa: B008
    livekit_api_key: p.Secret[str] = di.Provide["secrets.livekit.api_key"],  # noqa: B008
    livekit_api_secret: p.Secret[str] = di.Provide["secrets.livekit.api_secret"],  # noqa: B008
) -> None:
    """Run the LiveKit voice agent server.

    This server handles real-time voice assessments via LiveKit.
    Room metadata must contain the assessment context (attempt_id,
    objective info, prompts, rubric) as JSON.
    """
    import logging.config

    from socratic.llm.livekit import run_agent_server

    logging.config.dictConfig(logging_cf.model_dump())

    # Set boot config for worker processes (includes paths to load secrets)
    os.environ["__Socratic_BOOT"] = boot_cf.model_dump_json()

    click.echo("Starting LiveKit agent server")
    run_agent_server(
        livekit_wss_url=str(livekit_wss_url.get_secret_value()),
        livekit_api_key=livekit_api_key.get_secret_value(),
        livekit_api_secret=livekit_api_secret.get_secret_value(),
        devmode=dev,
    )
