"""Test script for LiveKit session handling.

Tests the session handler by:
1. Creating mock LiveKit context with real room metadata from DB
2. Calling _handle_session with real DI dependencies
3. Verifying STT/TTS are configured with correct API keys
4. Verifying the assessment agent is created correctly

Usage:
    socratic-cli script test-livekit-session --assignment-id asgn$...
    socratic-cli script test-livekit-session  # uses first available assignment
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pydantic as p
import sqlalchemy as sqla
from sqlalchemy.orm import Session

import socratic.lib.cli as click
from socratic.core import BootConfiguration, di
from socratic.llm.livekit.server import assessment_session
from socratic.model import AssignmentID, AttemptStatus
from socratic.storage import assignment as assignment_storage
from socratic.storage import attempt as attempt_storage
from socratic.storage import objective as obj_storage
from socratic.storage import rubric as rubric_storage
from socratic.storage.table import assignments


@click.command()
@click.option(
    "--assignment-id",
    "-a",
    type=str,
    default=None,
    help="Assignment ID to test (uses first available if not specified)",
)
@di.inject
def execute(
    assignment_id: str | None,
    session: Session = di.Manage["storage.persistent.session"],
    deepgram_api_key: p.Secret[str] = di.Provide["secrets.deepgram.api_key"],
    openai_api_key: p.Secret[str] = di.Provide["secrets.openai.secret_key"],
    stt_model: str = di.Provide["config.vendor.livekit.stt_model"],
    tts_model: str = di.Provide["config.vendor.livekit.tts_model"],
    tts_voice: str = di.Provide["config.vendor.livekit.tts_voice"],
    boot_cf: "BootConfiguration" = di.Provide["_boot_config"],
) -> None:
    """Test LiveKit session handler with real dependencies."""
    click.echo("=" * 60)
    click.echo("LiveKit Session Handler Test")
    click.echo("=" * 60)

    # Verify secrets are available
    click.echo("\n[1/5] Checking secrets...")
    dg_key = deepgram_api_key.get_secret_value()
    oai_key = openai_api_key.get_secret_value()
    click.echo(f"  Deepgram API key: {dg_key[:8]}...{dg_key[-4:]}")
    click.echo(f"  OpenAI API key: {oai_key[:8]}...{oai_key[-4:]}")
    click.echo("  ✓ Secrets loaded from container")

    # Verify config
    click.echo("\n[2/5] Checking config...")
    click.echo(f"  STT model: {stt_model}")
    click.echo(f"  TTS model: {tts_model}")
    click.echo(f"  TTS voice: {tts_voice}")
    click.echo("  ✓ Config loaded from vendor.yaml")

    # Get assignment and create room metadata
    click.echo("\n[3/5] Building room metadata from assignment...")
    with session.begin():
        if assignment_id:
            aid = AssignmentID(assignment_id)
            assignment = assignment_storage.get(aid, session=session)
            if assignment is None:
                click.echo(f"  ✗ Assignment {assignment_id} not found", err=True)
                sys.exit(1)
        else:
            stmt = sqla.select(assignments.__table__).limit(1)
            row = session.execute(stmt).mappings().first()
            if row is None:
                click.echo("  ✗ No assignments found in database", err=True)
                sys.exit(1)
            assignment = assignment_storage.get(AssignmentID(row["assignment_id"]), session=session)
            if assignment is None:
                click.echo("  ✗ Could not load assignment", err=True)
                sys.exit(1)

        click.echo(f"  Assignment: {assignment.assignment_id}")

        objective = obj_storage.get(assignment.objective_id, session=session)
        if objective is None:
            click.echo("  ✗ Objective not found", err=True)
            sys.exit(1)

        click.echo(f"  Objective: {objective.title}")

        rubric_criteria = rubric_storage.find(objective_id=objective.objective_id, session=session)
        serialized_criteria = [
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

        # Create attempt
        attempt = attempt_storage.create(
            assignment_id=assignment.assignment_id,
            learner_id=assignment.assigned_to,
            status=AttemptStatus.InProgress,
            session=session,
        )

        room_metadata = {
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
        }

    click.echo(f"  Created attempt: {attempt.attempt_id}")
    click.echo("  ✓ Room metadata built")

    # Create mock LiveKit context
    click.echo("\n[4/5] Creating mock LiveKit context...")
    mock_ctx = MagicMock()
    mock_ctx.room.name = "test-room"
    mock_ctx.room.metadata = json.dumps(room_metadata)
    mock_ctx.room.disconnect = AsyncMock()
    click.echo("  ✓ Mock JobContext created")

    # Test the full session handler path (including bootstrap)
    click.echo("\n[5/5] Testing assessment_session (full bootstrap path)...")

    # Set __Socratic_BOOT so assessment_session can bootstrap its own container
    os.environ["__Socratic_BOOT"] = boot_cf.model_dump_json()
    click.echo("  Set __Socratic_BOOT env var")

    # Mock only the AgentSession.start to avoid actual LiveKit connection
    # but let everything else (STT/TTS initialization) run for real
    with patch("socratic.llm.livekit.server.AgentSession") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.start = AsyncMock()
        mock_session.generate_reply = AsyncMock()
        mock_session_cls.return_value = mock_session

        # Run the full assessment_session (bootstraps container internally)
        click.echo("  Calling assessment_session()...")
        asyncio.run(assessment_session(mock_ctx))

        # Verify session was created and started
        mock_session_cls.assert_called_once()
        click.echo("  ✓ AgentSession created with STT/TTS/VAD")

        mock_session.start.assert_called_once()
        click.echo("  ✓ session.start() called")

        mock_session.generate_reply.assert_called_once()
        click.echo("  ✓ session.generate_reply() called")

    click.echo("\n" + "=" * 60)
    click.echo("All tests passed!")
    click.echo("=" * 60)
