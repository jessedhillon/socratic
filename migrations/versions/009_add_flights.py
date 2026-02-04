"""Add flights tables for prompt experimentation tracking.

Revision ID: 009
Revises: 008
Create Date: 2026-02-03

This migration adds tables for tracking prompt experiments:
- prompt_templates: Versioned Jinja2 templates
- survey_schemas: Schemas for feedback collection
- flights: Rendered template instances with metadata
- flight_surveys: Collected feedback for flights
"""

from alembic import op
from sqlalchemy import func as f
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.schema import Column, ForeignKey, UniqueConstraint
from sqlalchemy.types import Boolean, DateTime, Integer, String, Text

# revision identifiers, used by Alembic.
revision = "009_flights"
down_revision = "008_started_at_not_null"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create prompt_templates table
    op.create_table(
        "prompt_templates",
        Column("template_id", String(27), primary_key=True),
        Column("name", String, nullable=False),
        Column("version", Integer, nullable=False, server_default="1"),
        Column("content", Text, nullable=False),
        Column("description", Text, nullable=True),
        Column("is_active", Boolean, nullable=False, server_default="true"),
        Column("create_time", DateTime(timezone=True), nullable=False, server_default=f.now()),
        Column("update_time", DateTime(timezone=True), nullable=False, server_default=f.now()),
    )

    # Add unique constraint on (name, version) for prompt_templates
    op.create_unique_constraint(
        "uq_prompt_templates_name_version",
        "prompt_templates",
        ["name", "version"],
    )

    # Create survey_schemas table
    op.create_table(
        "survey_schemas",
        Column("schema_id", String(27), primary_key=True),
        Column("name", String, nullable=False),
        Column("dimensions", JSONB(astext_type=Text()), nullable=False, server_default="[]"),
        Column("is_default", Boolean, nullable=False, server_default="false"),
        Column("create_time", DateTime(timezone=True), nullable=False, server_default=f.now()),
        UniqueConstraint("name", name="uq_survey_schemas_name"),
    )

    # Create flights table
    op.create_table(
        "flights",
        Column("flight_id", String(27), primary_key=True),
        Column("template_id", String(27), ForeignKey("prompt_templates.template_id"), nullable=False),
        Column("created_by", String, nullable=False),
        Column("feature_flags", JSONB(astext_type=Text()), nullable=False, server_default="{}"),
        Column("context", JSONB(astext_type=Text()), nullable=False, server_default="{}"),
        Column("rendered_content", Text, nullable=False),
        Column("model_provider", String, nullable=False),
        Column("model_name", String, nullable=False),
        Column("model_config_data", JSONB(astext_type=Text()), nullable=False, server_default="{}"),
        Column("status", String, nullable=False, server_default="active"),
        Column("started_at", DateTime(timezone=True), nullable=False),
        Column("completed_at", DateTime(timezone=True), nullable=True),
        Column("attempt_id", String(27), ForeignKey("assessment_attempts.attempt_id"), nullable=True),
        Column("outcome_metadata", JSONB(astext_type=Text()), nullable=True),
        Column("create_time", DateTime(timezone=True), nullable=False, server_default=f.now()),
        Column("update_time", DateTime(timezone=True), nullable=False, server_default=f.now()),
    )

    # Create indexes for flights
    op.create_index("ix_flights_template_id", "flights", ["template_id"])
    op.create_index("ix_flights_attempt_id", "flights", ["attempt_id"])
    op.create_index("ix_flights_status", "flights", ["status"])
    op.create_index("ix_flights_created_by", "flights", ["created_by"])

    # Create flight_surveys table
    op.create_table(
        "flight_surveys",
        Column("survey_id", String(27), primary_key=True),
        Column("flight_id", String(27), ForeignKey("flights.flight_id"), nullable=False),
        Column("schema_id", String(27), ForeignKey("survey_schemas.schema_id"), nullable=True),
        Column("submitted_by", String, nullable=False),
        Column("ratings", JSONB(astext_type=Text()), nullable=False, server_default="{}"),
        Column("notes", Text, nullable=True),
        Column("tags", ARRAY(String), nullable=False, server_default="{}"),
        Column("create_time", DateTime(timezone=True), nullable=False, server_default=f.now()),
    )

    # Create indexes for flight_surveys
    op.create_index("ix_flight_surveys_flight_id", "flight_surveys", ["flight_id"])
    op.create_index("ix_flight_surveys_schema_id", "flight_surveys", ["schema_id"])
    op.create_index("ix_flight_surveys_submitted_by", "flight_surveys", ["submitted_by"])


def downgrade() -> None:
    # Drop indexes for flight_surveys
    op.drop_index("ix_flight_surveys_submitted_by", table_name="flight_surveys")
    op.drop_index("ix_flight_surveys_schema_id", table_name="flight_surveys")
    op.drop_index("ix_flight_surveys_flight_id", table_name="flight_surveys")

    # Drop flight_surveys table
    op.drop_table("flight_surveys")

    # Drop indexes for flights
    op.drop_index("ix_flights_created_by", table_name="flights")
    op.drop_index("ix_flights_status", table_name="flights")
    op.drop_index("ix_flights_attempt_id", table_name="flights")
    op.drop_index("ix_flights_template_id", table_name="flights")

    # Drop flights table
    op.drop_table("flights")

    # Drop survey_schemas table
    op.drop_table("survey_schemas")

    # Drop prompt_templates unique constraint and table
    op.drop_constraint("uq_prompt_templates_name_version", "prompt_templates")
    op.drop_table("prompt_templates")
