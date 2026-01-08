"""Initial schema for Socratic assessment system

Revision ID: 001_initial
Revises:
Create Date: 2026-01-07

"""

import typing as t

from alembic import op
from sqlalchemy import func as f
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.schema import Column, ForeignKey
from sqlalchemy.types import DateTime, Integer, Numeric, String, Text

from socratic.lib.sql import ExtendedOperations

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | t.Sequence[str] | None = None
depends_on: str | t.Sequence[str] | None = None


def upgrade() -> None:
    global op
    op = t.cast(ExtendedOperations, op)

    # Organizations
    op.create_table(
        "organizations",
        Column("organization_id", String(22), primary_key=True),
        Column("name", String, nullable=False),
        Column("slug", String, unique=True, nullable=False),
        Column("create_time", DateTime, server_default=f.now(), nullable=False),
        Column("update_time", DateTime, server_default=f.now(), onupdate=f.now(), nullable=False),
    )

    # Users
    op.create_table(
        "users",
        Column("user_id", String(22), primary_key=True),
        Column("email", String, unique=True, nullable=False),
        Column("name", String, nullable=False),
        Column("password_hash", String, nullable=True),
        Column("create_time", DateTime, server_default=f.now(), nullable=False),
        Column("update_time", DateTime, server_default=f.now(), onupdate=f.now(), nullable=False),
    )

    # Organization Memberships
    op.create_table(
        "organization_memberships",
        Column("user_id", String(22), ForeignKey("users.user_id"), primary_key=True),
        Column("organization_id", String(22), ForeignKey("organizations.organization_id"), primary_key=True),
        Column("role", String, nullable=False),
        Column("create_time", DateTime, server_default=f.now(), nullable=False),
        Column("update_time", DateTime, server_default=f.now(), onupdate=f.now(), nullable=False),
    )

    # Objectives
    op.create_table(
        "objectives",
        Column("objective_id", String(22), primary_key=True),
        Column("organization_id", String(22), ForeignKey("organizations.organization_id"), nullable=False),
        Column("created_by", String(22), ForeignKey("users.user_id"), nullable=False),
        Column("title", String, nullable=False),
        Column("description", Text, nullable=False),
        Column("scope_boundaries", Text, nullable=True),
        Column("time_expectation_minutes", Integer, nullable=True),
        Column("initial_prompts", ARRAY(String), server_default="{}"),
        Column("challenge_prompts", ARRAY(String), server_default="{}"),
        Column("extension_policy", String, server_default="disallowed", nullable=False),
        Column("status", String, server_default="draft", nullable=False),
        Column("create_time", DateTime, server_default=f.now(), nullable=False),
        Column("update_time", DateTime, server_default=f.now(), onupdate=f.now(), nullable=False),
    )

    # Strands
    op.create_table(
        "strands",
        Column("strand_id", String(22), primary_key=True),
        Column("organization_id", String(22), ForeignKey("organizations.organization_id"), nullable=False),
        Column("created_by", String(22), ForeignKey("users.user_id"), nullable=False),
        Column("name", String, nullable=False),
        Column("description", Text, nullable=True),
        Column("create_time", DateTime, server_default=f.now(), nullable=False),
        Column("update_time", DateTime, server_default=f.now(), onupdate=f.now(), nullable=False),
    )

    # Objectives in Strands (join table with position)
    op.create_table(
        "objectives_in_strands",
        Column("strand_id", String(22), ForeignKey("strands.strand_id"), primary_key=True),
        Column("objective_id", String(22), ForeignKey("objectives.objective_id"), primary_key=True),
        Column("position", Integer, nullable=False),
    )

    # Objective Dependencies
    op.create_table(
        "objective_dependencies",
        Column("objective_id", String(22), ForeignKey("objectives.objective_id"), primary_key=True),
        Column("depends_on_objective_id", String(22), ForeignKey("objectives.objective_id"), primary_key=True),
        Column("dependency_type", String, server_default="hard", nullable=False),
    )

    # Rubric Criteria
    op.create_table(
        "rubric_criteria",
        Column("criterion_id", String(22), primary_key=True),
        Column("objective_id", String(22), ForeignKey("objectives.objective_id"), nullable=False),
        Column("name", String, nullable=False),
        Column("description", Text, nullable=False),
        Column("evidence_indicators", ARRAY(String), server_default="{}"),
        Column("failure_modes", JSONB, server_default="[]"),
        Column("grade_thresholds", JSONB, server_default="[]"),
        Column("weight", Numeric(4, 2), server_default="1.0", nullable=False),
    )

    # Assignments
    op.create_table(
        "assignments",
        Column("assignment_id", String(22), primary_key=True),
        Column("organization_id", String(22), ForeignKey("organizations.organization_id"), nullable=False),
        Column("objective_id", String(22), ForeignKey("objectives.objective_id"), nullable=False),
        Column("assigned_by", String(22), ForeignKey("users.user_id"), nullable=False),
        Column("assigned_to", String(22), ForeignKey("users.user_id"), nullable=False),
        Column("available_from", DateTime, nullable=True),
        Column("available_until", DateTime, nullable=True),
        Column("max_attempts", Integer, server_default="1", nullable=False),
        Column("retake_policy", String, server_default="none", nullable=False),
        Column("retake_delay_hours", Integer, nullable=True),
        Column("create_time", DateTime, server_default=f.now(), nullable=False),
        Column("update_time", DateTime, server_default=f.now(), onupdate=f.now(), nullable=False),
    )

    # Assessment Attempts
    op.create_table(
        "assessment_attempts",
        Column("attempt_id", String(22), primary_key=True),
        Column("assignment_id", String(22), ForeignKey("assignments.assignment_id"), nullable=False),
        Column("learner_id", String(22), ForeignKey("users.user_id"), nullable=False),
        Column("status", String, server_default="not_started", nullable=False),
        Column("started_at", DateTime, nullable=True),
        Column("completed_at", DateTime, nullable=True),
        Column("grade", String, nullable=True),
        Column("confidence_score", Numeric(5, 4), nullable=True),
        Column("audio_url", String, nullable=True),
        Column("create_time", DateTime, server_default=f.now(), nullable=False),
    )

    # Transcript Segments
    op.create_table(
        "transcript_segments",
        Column("segment_id", String(22), primary_key=True),
        Column("attempt_id", String(22), ForeignKey("assessment_attempts.attempt_id"), nullable=False),
        Column("utterance_type", String, nullable=False),
        Column("content", Text, nullable=False),
        Column("start_time", DateTime, nullable=False),
        Column("end_time", DateTime, nullable=True),
        Column("confidence", Numeric(5, 4), nullable=True),
        Column("prompt_index", Integer, nullable=True),
    )

    # Evaluation Results
    op.create_table(
        "evaluation_results",
        Column("evaluation_id", String(22), primary_key=True),
        Column("attempt_id", String(22), ForeignKey("assessment_attempts.attempt_id"), nullable=False),
        Column("evidence_mappings", JSONB, server_default="[]"),
        Column("flags", ARRAY(String), server_default="{}"),
        Column("strengths", ARRAY(String), server_default="{}"),
        Column("gaps", ARRAY(String), server_default="{}"),
        Column("reasoning_summary", Text, nullable=True),
        Column("create_time", DateTime, server_default=f.now(), nullable=False),
    )

    # Educator Overrides
    op.create_table(
        "educator_overrides",
        Column("override_id", String(22), primary_key=True),
        Column("attempt_id", String(22), ForeignKey("assessment_attempts.attempt_id"), nullable=False),
        Column("educator_id", String(22), ForeignKey("users.user_id"), nullable=False),
        Column("new_grade", String, nullable=False),
        Column("reason", Text, nullable=False),
        Column("original_grade", String, nullable=True),
        Column("feedback", Text, nullable=True),
        Column("create_time", DateTime, server_default=f.now(), nullable=False),
    )

    # Create indexes for common queries
    op.create_index("ix_organization_memberships_org_id", "organization_memberships", ["organization_id"])
    op.create_index("ix_objectives_organization_id", "objectives", ["organization_id"])
    op.create_index("ix_objectives_created_by", "objectives", ["created_by"])
    op.create_index("ix_strands_organization_id", "strands", ["organization_id"])
    op.create_index("ix_rubric_criteria_objective_id", "rubric_criteria", ["objective_id"])
    op.create_index("ix_assignments_organization_id", "assignments", ["organization_id"])
    op.create_index("ix_assignments_objective_id", "assignments", ["objective_id"])
    op.create_index("ix_assignments_assigned_to", "assignments", ["assigned_to"])
    op.create_index("ix_assessment_attempts_assignment_id", "assessment_attempts", ["assignment_id"])
    op.create_index("ix_assessment_attempts_learner_id", "assessment_attempts", ["learner_id"])
    op.create_index("ix_transcript_segments_attempt_id", "transcript_segments", ["attempt_id"])
    op.create_index("ix_evaluation_results_attempt_id", "evaluation_results", ["attempt_id"])
    op.create_index("ix_educator_overrides_attempt_id", "educator_overrides", ["attempt_id"])


def downgrade() -> None:
    global op
    op = t.cast(ExtendedOperations, op)

    # Drop indexes
    op.drop_index("ix_educator_overrides_attempt_id")
    op.drop_index("ix_evaluation_results_attempt_id")
    op.drop_index("ix_transcript_segments_attempt_id")
    op.drop_index("ix_assessment_attempts_learner_id")
    op.drop_index("ix_assessment_attempts_assignment_id")
    op.drop_index("ix_assignments_assigned_to")
    op.drop_index("ix_assignments_objective_id")
    op.drop_index("ix_assignments_organization_id")
    op.drop_index("ix_rubric_criteria_objective_id")
    op.drop_index("ix_strands_organization_id")
    op.drop_index("ix_objectives_created_by")
    op.drop_index("ix_objectives_organization_id")
    op.drop_index("ix_organization_memberships_org_id")

    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table("educator_overrides")
    op.drop_table("evaluation_results")
    op.drop_table("transcript_segments")
    op.drop_table("assessment_attempts")
    op.drop_table("assignments")
    op.drop_table("rubric_criteria")
    op.drop_table("objective_dependencies")
    op.drop_table("objectives_in_strands")
    op.drop_table("strands")
    op.drop_table("objectives")
    op.drop_table("organization_memberships")
    op.drop_table("users")
    op.drop_table("organizations")
