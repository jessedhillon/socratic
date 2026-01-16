"""Add word_timings table and video_url to assessment_attempts.

Revision ID: 007
Revises: 006
Create Date: 2025-01-16
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "007_word_timings"
down_revision = "006_timestamptz"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add video_url column to assessment_attempts
    op.add_column(
        "assessment_attempts",
        sa.Column("video_url", sa.String(), nullable=True),
    )

    # Create word_timings table
    op.create_table(
        "word_timings",
        sa.Column("word_timing_id", sa.String(length=27), nullable=False),
        sa.Column("segment_id", sa.String(length=27), nullable=False),
        sa.Column("word", sa.String(), nullable=False),
        sa.Column("start_offset_ms", sa.Integer(), nullable=False),
        sa.Column("end_offset_ms", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.ForeignKeyConstraint(
            ["segment_id"],
            ["transcript_segments.segment_id"],
            name="fk_word_timings_segment_id",
        ),
        sa.PrimaryKeyConstraint("word_timing_id"),
    )

    # Create index on segment_id for faster lookups
    op.create_index(
        "ix_word_timings_segment_id",
        "word_timings",
        ["segment_id"],
    )


def downgrade() -> None:
    # Drop index
    op.drop_index("ix_word_timings_segment_id", table_name="word_timings")

    # Drop word_timings table
    op.drop_table("word_timings")

    # Drop video_url column
    op.drop_column("assessment_attempts", "video_url")
