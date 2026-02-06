"""Setup the default assessment survey schema.

Creates the "assessment_feedback" survey schema in the flights service
via HTTP API. This script treats flights as an external vendor service.

Usage:
    socratic-cli script setup-assessment-survey
    socratic-cli script setup-assessment-survey --flights-url http://localhost:8002

The schema defines dimensions for capturing feedback on assessment sessions:
- probing_depth: Quality of follow-up questions
- validation_level: How well responses were acknowledged
- pacing: Appropriate speed of the interaction
- challenge_level: Appropriate difficulty of questions
- notes: Free-form feedback
"""

from __future__ import annotations

import httpx

import socratic.lib.cli as click
from socratic.core import di
from socratic.core.config import Settings
from socratic.lib.vendor.flights import FlightsClientSync
from socratic.model import RatingSpec, RatingUISpec, SurveyDimension, TextSpec


def _get_default_dimensions() -> list[SurveyDimension]:
    """Return the default assessment feedback dimensions."""
    return [
        SurveyDimension(
            name="probing_depth",
            label="Did the tutor ask meaningful follow-up questions?",
            required=True,
            help="Focus on whether follow-ups advanced understanding, not just quantity.",
            spec=RatingSpec(
                min=0,
                max=5,
                step=1,
                anchors={
                    "0": "None / purely procedural",
                    "3": "Some meaningful follow-ups",
                    "5": "Consistently incisive follow-ups",
                },
                ui=RatingUISpec(control="slider", show_value=True),
            ),
        ),
        SurveyDimension(
            name="validation_level",
            label="How well did the tutor acknowledge your responses?",
            required=True,
            help="Did the tutor show they understood what you said before moving on?",
            spec=RatingSpec(
                min=0,
                max=5,
                step=1,
                anchors={
                    "0": "Ignored responses entirely",
                    "3": "Basic acknowledgment",
                    "5": "Thoughtful reflection on each response",
                },
                ui=RatingUISpec(control="slider", show_value=True),
            ),
        ),
        SurveyDimension(
            name="pacing",
            label="Was the conversation paced appropriately?",
            required=True,
            help="Did you have enough time to think, without long awkward pauses?",
            spec=RatingSpec(
                min=0,
                max=5,
                step=1,
                anchors={
                    "0": "Far too rushed or too slow",
                    "3": "Acceptable pace",
                    "5": "Perfect pacing throughout",
                },
                ui=RatingUISpec(control="slider", show_value=True),
            ),
        ),
        SurveyDimension(
            name="challenge_level",
            label="Were the questions appropriately challenging?",
            required=True,
            help="Did the tutor adjust difficulty based on your demonstrated understanding?",
            spec=RatingSpec(
                min=0,
                max=5,
                step=1,
                anchors={
                    "0": "Too easy or too hard throughout",
                    "3": "Generally appropriate",
                    "5": "Perfectly calibrated to my level",
                },
                ui=RatingUISpec(control="slider", show_value=True),
            ),
        ),
        SurveyDimension(
            name="notes",
            label="Any additional feedback?",
            required=False,
            help="Share anything else about your experience with this assessment.",
            spec=TextSpec(max_length=1000, placeholder="Optional comments..."),
        ),
    ]


@click.command()
@click.option(
    "--flights-url",
    default=None,
    help="Flights service URL (default: from config)",
)
@di.inject
def execute(
    flights_url: str | None,
    config: Settings = di.Provide["config", di.as_(Settings)],
) -> None:
    """Create the default assessment feedback survey schema."""
    # Get flights URL from config if not provided
    if flights_url is None:
        flights_url = config.vendor.flights.base_url

    click.echo(f"Connecting to flights service at {flights_url}")

    client = FlightsClientSync(flights_url)
    dimensions = _get_default_dimensions()

    click.echo(f"Creating assessment_feedback schema with {len(dimensions)} dimensions:")
    for dim in dimensions:
        req = "*" if dim.required else " "
        click.echo(f"  {req} {dim.name:20s} ({dim.spec.kind:10s})")

    try:
        result = client.create_survey_schema(
            name="assessment_feedback",
            dimensions=dimensions,
            is_default=True,
        )
        click.echo("\nCreated schema:")
        click.echo(f"  ID:      {result.schema_id}")
        click.echo(f"  Name:    {result.name}")
        click.echo(f"  Version: {result.version}")
        click.echo(f"  Hash:    {result.dimensions_hash[:16]}...")
        click.echo(f"  Default: {result.is_default}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 409:
            click.echo("\nSchema 'assessment_feedback' already exists.")
            click.echo("To update dimensions, modify the schema via the API.")
        else:
            click.echo(f"\nError: {e.response.status_code} - {e.response.text}")
            raise click.ClickException(f"Failed to create schema: {e}") from e
