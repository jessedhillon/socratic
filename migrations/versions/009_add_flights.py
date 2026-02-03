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

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "009_flights"
down_revision = "008_started_at_not_null"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create prompt_templates table
    op.create_table(
        "prompt_templates",
        sa.Column("template_id", sa.String(length=27), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "create_time",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "update_time",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("template_id"),
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
        sa.Column("schema_id", sa.String(length=27), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "dimensions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "create_time",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("schema_id"),
        sa.UniqueConstraint("name", name="uq_survey_schemas_name"),
    )

    # Create flights table
    op.create_table(
        "flights",
        sa.Column("flight_id", sa.String(length=27), nullable=False),
        sa.Column("template_id", sa.String(length=27), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column(
            "feature_flags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("rendered_content", sa.Text(), nullable=False),
        sa.Column("model_provider", sa.String(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=False),
        sa.Column(
            "model_config_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="'active'"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_id", sa.String(length=27), nullable=True),
        sa.Column(
            "outcome_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "create_time",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "update_time",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["prompt_templates.template_id"],
            name="fk_flights_template_id",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["assessment_attempts.attempt_id"],
            name="fk_flights_attempt_id",
        ),
        sa.PrimaryKeyConstraint("flight_id"),
    )

    # Create indexes for flights
    op.create_index("ix_flights_template_id", "flights", ["template_id"])
    op.create_index("ix_flights_attempt_id", "flights", ["attempt_id"])
    op.create_index("ix_flights_status", "flights", ["status"])
    op.create_index("ix_flights_created_by", "flights", ["created_by"])

    # Create flight_surveys table
    op.create_table(
        "flight_surveys",
        sa.Column("survey_id", sa.String(length=27), nullable=False),
        sa.Column("flight_id", sa.String(length=27), nullable=False),
        sa.Column("schema_id", sa.String(length=27), nullable=True),
        sa.Column("submitted_by", sa.String(), nullable=False),
        sa.Column(
            "ratings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "create_time",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["flight_id"],
            ["flights.flight_id"],
            name="fk_flight_surveys_flight_id",
        ),
        sa.ForeignKeyConstraint(
            ["schema_id"],
            ["survey_schemas.schema_id"],
            name="fk_flight_surveys_schema_id",
        ),
        sa.PrimaryKeyConstraint("survey_id"),
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
