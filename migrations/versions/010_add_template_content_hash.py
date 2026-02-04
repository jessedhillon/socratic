"""Add content_hash column to prompt_templates.

Revision ID: 010
Revises: 009
Create Date: 2026-02-04

Adds a SHA-256 content hash for content-addressed template resolution.
Backfills existing rows with computed hashes.
"""

import hashlib

import jinja2
from alembic import op
from sqlalchemy import text
from sqlalchemy.schema import Column
from sqlalchemy.types import String

# revision identifiers, used by Alembic.
revision = "010_template_content_hash"
down_revision = "009_flights"
branch_labels = None
depends_on = None

_jinja_env = jinja2.Environment(autoescape=False)


def _hash_content(content: str) -> str:
    try:
        ast = _jinja_env.parse(content.strip())
        canonical = repr(ast.body)
    except jinja2.TemplateSyntaxError:
        canonical = content.strip()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def upgrade() -> None:
    # Add content_hash as nullable first
    op.add_column("prompt_templates", Column("content_hash", String(64), nullable=True))

    # Backfill existing rows
    conn = op.get_bind()
    rows = conn.execute(text("SELECT template_id, content FROM prompt_templates")).fetchall()
    for row in rows:
        content_hash = _hash_content(row.content)
        conn.execute(
            text("UPDATE prompt_templates SET content_hash = :hash WHERE template_id = :id"),
            {"hash": content_hash, "id": row.template_id},
        )

    # Make non-nullable
    op.alter_column("prompt_templates", "content_hash", nullable=False)

    # Add index for (name, content_hash) lookups
    op.create_index("ix_prompt_templates_name_content_hash", "prompt_templates", ["name", "content_hash"])


def downgrade() -> None:
    op.drop_index("ix_prompt_templates_name_content_hash", table_name="prompt_templates")
    op.drop_column("prompt_templates", "content_hash")
