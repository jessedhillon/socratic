"""Demo script for the flights (prompt experimentation tracking) module.

Demonstrates the full workflow:
1. Create a prompt template with Jinja2 variables
2. Create a survey schema for collecting feedback
3. Start a "flight" - a rendered instance of the template
4. Complete the flight with outcome metadata
5. Submit a survey rating the flight

Usage:
    socratic-cli script demo-flights
    socratic-cli script demo-flights --cleanup  # removes demo data after
"""

from __future__ import annotations

import datetime
import typing as t

from sqlalchemy.orm import Session

import socratic.lib.cli as click
from socratic.core import di
from socratic.model import ChoiceOption, ChoiceSpec, RatingSpec, SurveyDimension, TextSpec
from socratic.storage import flight as flight_storage


@click.command()
@click.option(
    "--cleanup",
    is_flag=True,
    default=False,
    help="Clean up demo data after running",
)
@di.inject
def execute(
    cleanup: bool,
    session: Session = di.Manage["storage.persistent.session"],
) -> None:
    """Demonstrate the flights prompt experimentation workflow."""
    click.echo("=" * 70)
    click.echo("Flights Demo: Prompt Experimentation Tracking")
    click.echo("=" * 70)

    # Track created IDs for cleanup
    created_ids: dict[str, t.Any] = {}

    # -------------------------------------------------------------------------
    # Step 1: Create a Prompt Template
    # -------------------------------------------------------------------------
    click.echo("\n" + "-" * 70)
    click.echo("STEP 1: Create a Prompt Template")
    click.echo("-" * 70)

    template_content = """\
You are {{ persona }}, an AI tutor helping a student learn about {{ topic }}.

Your teaching style should be {{ style }}.

The student's current level is: {{ level }}

{% if focus_areas %}
Focus especially on these areas:
{% for area in focus_areas %}
- {{ area }}
{% endfor %}
{% endif %}

Begin by introducing the topic and gauging the student's existing knowledge."""

    click.echo("\nTemplate content (Jinja2):")
    click.echo("-" * 40)
    for i, line in enumerate(template_content.split("\n"), 1):
        click.echo(f"  {i:2d} | {line}")
    click.echo("-" * 40)

    with session.begin():
        # Check if template exists - if so, we'll create a new version
        existing = flight_storage.get_template(name="demo_tutor_system", session=session)
        template = flight_storage.create_template(
            name="demo_tutor_system",
            content=template_content,
            description="Demo template for AI tutoring with configurable persona and style",
            session=session,
        )
        created_ids["template_id"] = template.template_id

    if existing:
        click.echo(f"\nCreated new version of template (was v{existing.version}):")
    else:
        click.echo("\nCreated template:")
    click.echo(f"  ID:      {template.template_id}")
    click.echo(f"  Name:    {template.name}")
    click.echo(f"  Version: {template.version}")

    # -------------------------------------------------------------------------
    # Step 2: Create a Survey Schema
    # -------------------------------------------------------------------------
    click.echo("\n" + "-" * 70)
    click.echo("STEP 2: Create a Survey Schema")
    click.echo("-" * 70)

    survey_dimensions = [
        SurveyDimension(
            name="clarity",
            label="How clear was the tutor's explanation?",
            required=True,
            spec=RatingSpec(
                min=1,
                max=5,
                anchors={
                    "1": "Very unclear",
                    "3": "Somewhat clear",
                    "5": "Crystal clear",
                },
            ),
        ),
        SurveyDimension(
            name="engagement",
            label="How engaging was the interaction?",
            required=True,
            spec=RatingSpec(min=1, max=5),
        ),
        SurveyDimension(
            name="pacing",
            label="Was the pacing appropriate?",
            required=False,
            spec=ChoiceSpec(
                options=[
                    ChoiceOption(value="too_slow", label="Too slow"),
                    ChoiceOption(value="just_right", label="Just right"),
                    ChoiceOption(value="too_fast", label="Too fast"),
                ],
            ),
        ),
        SurveyDimension(
            name="notes",
            label="Additional feedback",
            required=False,
            spec=TextSpec(max_length=500),
        ),
    ]

    click.echo("\nSurvey dimensions:")
    for dim in survey_dimensions:
        req = "*" if dim.required else " "
        click.echo(f"  {req} {dim.name:12s} ({dim.spec.kind:12s}): {dim.label}")

    with session.begin():
        # Reuse existing schema if it exists (schemas don't version like templates)
        schema = flight_storage.get_survey_schema(name="demo_tutor_feedback", session=session)
        if schema:
            click.echo("\nReusing existing survey schema:")
        else:
            schema = flight_storage.create_survey_schema(
                name="demo_tutor_feedback",
                dimensions=survey_dimensions,
                session=session,
            )
            click.echo("\nCreated survey schema:")
        created_ids["schema_id"] = schema.schema_id

    click.echo(f"  ID:   {schema.schema_id}")
    click.echo(f"  Name: {schema.name}")

    # -------------------------------------------------------------------------
    # Step 3: Start a Flight
    # -------------------------------------------------------------------------
    click.echo("\n" + "-" * 70)
    click.echo("STEP 3: Start a Flight (Rendered Prompt Instance)")
    click.echo("-" * 70)

    # These are the variables we'll use to render the template
    context = {
        "persona": "Professor Ada",
        "topic": "recursion in programming",
        "style": "Socratic - ask guiding questions rather than giving direct answers",
        "level": "intermediate",
        "focus_areas": ["base cases", "stack overflow prevention", "tail recursion"],
    }

    # Feature flags track experimental variations
    feature_flags = {
        "persona_variant": "formal_academic",
        "style_variant": "socratic_v2",
        "include_examples": True,
    }

    click.echo("\nTemplate context (variables):")
    for key, value in context.items():
        if isinstance(value, list):
            click.echo(f"  {key}:")
            for item in value:
                click.echo(f"    - {item}")
        else:
            click.echo(f"  {key}: {value}")

    click.echo("\nFeature flags (experiment tracking):")
    for key, value in feature_flags.items():
        click.echo(f"  {key}: {value}")

    with session.begin():
        flight = flight_storage.create_flight(
            template_id=template.template_id,
            created_by="demo_script",
            model_provider="openai",
            model_name="gpt-4.1",
            started_at=datetime.datetime.now(datetime.UTC),
            feature_flags=feature_flags,
            context=context,
            model_config={"temperature": 0.7, "max_tokens": 2048},
            session=session,
        )
        created_ids["flight_id"] = flight.flight_id

    click.echo("\nCreated flight:")
    click.echo(f"  ID:       {flight.flight_id}")
    click.echo(f"  Status:   {flight.status.value}")
    click.echo(f"  Provider: {flight.model_provider}")
    click.echo(f"  Model:    {flight.model_name}")

    # Render the template for display (rendered_content is computed on-the-fly via API)
    rendered_content = _render_template(template_content, context)
    click.echo("\nRendered prompt:")
    click.echo("-" * 40)
    for line in rendered_content.split("\n"):
        click.echo(f"  {line}")
    click.echo("-" * 40)

    # -------------------------------------------------------------------------
    # Step 4: Complete the Flight
    # -------------------------------------------------------------------------
    click.echo("\n" + "-" * 70)
    click.echo("STEP 4: Complete the Flight")
    click.echo("-" * 70)

    outcome_metadata = {
        "turns": 12,
        "duration_seconds": 847,
        "tokens_used": {"prompt": 1523, "completion": 2891},
        "learner_reached_understanding": True,
        "topics_covered": ["base cases", "stack overflow", "recursive vs iterative"],
    }

    click.echo("\nOutcome metadata:")
    for key, value in outcome_metadata.items():
        click.echo(f"  {key}: {value}")

    with session.begin():
        flight_storage.complete_flight(
            flight.flight_id,
            outcome_metadata=outcome_metadata,
            session=session,
        )

        # Reload to see updated status
        updated_flight = flight_storage.get_flight(flight.flight_id, session=session)
        assert updated_flight is not None

    click.echo("\nFlight completed:")
    click.echo(f"  Status:       {updated_flight.status.value}")
    click.echo(f"  Completed at: {updated_flight.completed_at}")

    # -------------------------------------------------------------------------
    # Step 5: Submit a Survey
    # -------------------------------------------------------------------------
    click.echo("\n" + "-" * 70)
    click.echo("STEP 5: Submit a Survey")
    click.echo("-" * 70)

    ratings = {
        "clarity": 4,
        "engagement": 5,
        "pacing": "just_right",
        "notes": "Great use of Socratic questioning! The recursion examples were helpful.",
    }

    click.echo("\nSurvey ratings:")
    for key, value in ratings.items():
        click.echo(f"  {key}: {value}")

    with session.begin():
        survey = flight_storage.create_survey(
            flight_id=flight.flight_id,
            submitted_by="demo_reviewer",
            ratings=ratings,
            schema_id=schema.schema_id,
            notes="Overall excellent session",
            tags=["recursion", "socratic", "positive"],
            session=session,
        )
        created_ids["survey_id"] = survey.survey_id

    click.echo("\nCreated survey:")
    click.echo(f"  ID:           {survey.survey_id}")
    click.echo(f"  Submitted by: {survey.submitted_by}")
    click.echo(f"  Tags:         {', '.join(survey.tags)}")

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    click.echo("\n" + "=" * 70)
    click.echo("SUMMARY: What Was Created")
    click.echo("=" * 70)

    click.echo(f"""
The flights module tracks prompt experiments:

  Template ({template.template_id})
    A versioned Jinja2 template. Creating a new version with the same
    name auto-increments the version number.

  Survey Schema ({schema.schema_id})
    Defines the dimensions for collecting structured feedback.
    Can be reused across multiple flights.

  Flight ({flight.flight_id})
    A single "flight" of a prompt - the rendered template with all its
    context, feature flags, model config, and outcome data. This is the
    core unit for A/B testing and prompt optimization.

  Survey ({survey.survey_id})
    Human feedback on the flight, structured according to the schema.
    Multiple surveys can be attached to one flight.

Use this data to:
  - Compare prompt variants (via feature_flags)
  - Track which templates produce better outcomes
  - Correlate survey feedback with outcome metrics
  - Version and audit prompt changes over time
""")

    # -------------------------------------------------------------------------
    # Cleanup (optional)
    # -------------------------------------------------------------------------
    if cleanup:
        click.echo("-" * 70)
        click.echo("Cleaning up demo data...")
        click.echo("-" * 70)
        click.echo("\n(Note: In a real app, you'd delete the records here)")
        click.echo("For this demo, the data remains in the database for inspection.")

    click.echo("\n" + "=" * 70)
    click.echo("Demo complete!")
    click.echo("=" * 70)


def _render_template(template_content: str, context: dict[str, t.Any]) -> str:
    """Simple Jinja2 template rendering."""
    import jinja2

    env = jinja2.Environment(autoescape=False)
    template = env.from_string(template_content)
    return template.render(**context)
