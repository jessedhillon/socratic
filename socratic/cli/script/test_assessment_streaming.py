"""E2E test for assessment streaming flow.

Tests the full assessment streaming pipeline:
1. Start an assessment
2. Subscribe to the stream
3. Send learner messages
4. Complete the assessment

Usage:
    socratic-cli script test-assessment-streaming --assignment-id asgn$...
    socratic-cli script test-assessment-streaming  # uses first available assignment
"""

from __future__ import annotations

import asyncio
import sys
import typing as t

import jinja2
from langchain_core.language_models import BaseChatModel
from sqlalchemy.orm import Session

import socratic.lib.cli as click
from socratic.core import di
from socratic.llm.assessment import PostgresCheckpointer, start_assessment
from socratic.model import AssignmentID, AttemptID, AttemptStatus
from socratic.storage import assignment as assignment_storage
from socratic.storage import attempt as attempt_storage
from socratic.storage import objective as obj_storage
from socratic.storage import rubric as rubric_storage
from socratic.storage.streaming import AssessmentStreamBroker, StreamEvent


@click.command()
@click.option(
    "--assignment-id",
    "-a",
    type=str,
    default=None,
    help="Assignment ID to test (uses first available if not specified)",
)
@click.option(
    "--interactive",
    "-i",
    is_flag=True,
    default=False,
    help="Interactive mode: prompt for learner responses",
)
@di.inject
def execute(
    assignment_id: str | None,
    interactive: bool,
    session: Session = di.Manage["storage.persistent.session"],
    model: BaseChatModel = di.Provide["llm.dialogue_model"],
    env: jinja2.Environment = di.Provide["template.llm"],
    broker: AssessmentStreamBroker = di.Provide["storage.streaming.broker"],
) -> None:
    """Run an end-to-end assessment streaming test."""
    click.echo("=" * 60)
    click.echo("Assessment Streaming E2E Test")
    click.echo("=" * 60)

    # Get assignment
    with session.begin():
        if assignment_id:
            aid = AssignmentID(assignment_id)
            assignment = assignment_storage.get(aid, session=session)
            if assignment is None:
                click.echo(f"Error: Assignment {assignment_id} not found", err=True)
                sys.exit(1)
        else:
            # Find first available assignment
            import sqlalchemy as sqla

            from socratic.storage.table import assignments

            stmt = sqla.select(assignments.__table__).limit(1)
            row = session.execute(stmt).mappings().first()
            if row is None:
                click.echo("Error: No assignments found in database", err=True)
                sys.exit(1)
            assignment = assignment_storage.get(AssignmentID(row["assignment_id"]), session=session)
            if assignment is None:
                click.echo("Error: Could not load assignment", err=True)
                sys.exit(1)

        click.echo(f"\nUsing assignment: {assignment.assignment_id}")

        # Get objective
        objective = obj_storage.get(assignment.objective_id, session=session)
        if objective is None:
            click.echo("Error: Objective not found", err=True)
            sys.exit(1)

        click.echo(f"Objective: {objective.title}")
        click.echo(f"Description: {objective.description[:100]}...")

        # Get rubric
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

        click.echo(f"Rubric criteria: {len(serialized_criteria)}")

        # Create attempt
        attempt = attempt_storage.create(
            assignment_id=assignment.assignment_id,
            learner_id=assignment.assigned_to,
            status=AttemptStatus.InProgress,
            session=session,
        )
        attempt_id = attempt.attempt_id

        # Extract values needed after transaction
        objective_id = str(objective.objective_id)
        objective_title = objective.title
        objective_description = objective.description
        initial_prompts = objective.initial_prompts
        scope_boundaries = objective.scope_boundaries
        time_expectation_minutes = objective.time_expectation_minutes
        challenge_prompts = objective.challenge_prompts
        extension_policy = objective.extension_policy.value

    click.echo(f"\nCreated attempt: {attempt_id}")
    click.echo("\n" + "-" * 60)
    click.echo("Starting assessment orientation...")
    click.echo("-" * 60 + "\n")

    # Run the async streaming flow
    asyncio.run(
        _run_streaming_flow(
            attempt_id=attempt_id,
            objective_id=objective_id,
            objective_title=objective_title,
            objective_description=objective_description,
            initial_prompts=initial_prompts,
            serialized_criteria=serialized_criteria,
            scope_boundaries=scope_boundaries,
            time_expectation_minutes=time_expectation_minutes,
            challenge_prompts=challenge_prompts,
            extension_policy=extension_policy,
            interactive=interactive,
            model=model,
            env=env,
            broker=broker,
        )
    )

    click.echo("\n" + "=" * 60)
    click.echo("Test completed!")
    click.echo("=" * 60)


async def _run_streaming_flow(
    attempt_id: AttemptID,
    objective_id: str,
    objective_title: str,
    objective_description: str,
    initial_prompts: list[str],
    serialized_criteria: list[dict[str, t.Any]],
    scope_boundaries: str | None,
    time_expectation_minutes: int | None,
    challenge_prompts: list[str] | None,
    extension_policy: str,
    interactive: bool,
    model: BaseChatModel,
    env: jinja2.Environment,
    broker: AssessmentStreamBroker,
) -> None:
    """Run the async streaming portion of the test."""
    checkpointer = PostgresCheckpointer()

    # Start a subscriber task
    subscriber_task = asyncio.create_task(_subscribe_and_print(attempt_id, broker))

    # Give subscriber time to connect
    await asyncio.sleep(0.1)

    click.echo("[AI Interviewer]: ", nl=False)

    # Stream orientation
    full_message = ""
    try:
        async for token in start_assessment(
            attempt_id=attempt_id,
            objective_id=objective_id,
            objective_title=objective_title,
            objective_description=objective_description,
            initial_prompts=initial_prompts,
            rubric_criteria=serialized_criteria,
            checkpointer=checkpointer,
            model=model,
            env=env,
            scope_boundaries=scope_boundaries,
            time_expectation_minutes=time_expectation_minutes,
            challenge_prompts=challenge_prompts,
            extension_policy=extension_policy,
        ):
            full_message += token
            click.echo(token, nl=False)
            await broker.publish(attempt_id, StreamEvent(event_type="token", data={"content": token}))

        click.echo("\n")

        # Publish message done
        await broker.publish(attempt_id, StreamEvent(event_type="message_done", data={}))

        click.echo(f"\n[Orientation complete - {len(full_message)} characters streamed]")

    except Exception as e:
        click.echo(f"\n\nError during orientation: {e}", err=True)
        await broker.publish(
            attempt_id,
            StreamEvent(event_type="error", data={"message": str(e), "recoverable": False}),
        )

    # Simulate learner response
    if interactive:
        click.echo("\n" + "-" * 40)
        learner_input = click.prompt("Your response (or 'quit' to end)")
        if learner_input.lower() != "quit":
            click.echo(f"\n[Learner]: {learner_input}")
    else:
        click.echo("\n[Simulated Learner]: I understand the task. Let me explain my understanding of ratios...")

    # Complete the assessment
    click.echo("\n" + "-" * 60)
    click.echo("Completing assessment...")
    await broker.publish(attempt_id, StreamEvent(event_type="assessment_complete", data={}))
    await broker.close_stream(attempt_id)

    # Cancel subscriber
    subscriber_task.cancel()
    try:
        await subscriber_task
    except asyncio.CancelledError:
        pass


async def _subscribe_and_print(attempt_id: AttemptID, broker: AssessmentStreamBroker) -> None:
    """Subscribe to stream and log events (for debugging)."""
    try:
        async for _event_id, event in broker.subscribe(attempt_id):
            if event.event_type == "token":
                # Tokens are already printed by the main flow
                pass
            elif event.event_type == "message_done":
                click.echo("\n[Stream: message_done]", err=True)
            elif event.event_type == "assessment_complete":
                click.echo("[Stream: assessment_complete]", err=True)
                break
            elif event.event_type == "error":
                click.echo(f"[Stream: error] {event.data}", err=True)
                break
    except asyncio.CancelledError:
        pass
