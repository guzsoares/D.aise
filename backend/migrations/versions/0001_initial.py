"""schema inicial: projects, prompts, default_prompts, llm_config

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompts",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.Text(), server_default=""),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "default_prompts",
        sa.Column("type", sa.String(), primary_key=True),
        sa.Column(
            "prompt_id",
            sa.String(length=64),
            sa.ForeignKey("prompts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("folder_name", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), server_default=""),
        sa.Column("path", sa.Text(), server_default=""),
        sa.Column("tree", sa.Text(), server_default=""),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("readme", sa.Text(), server_default=""),
        sa.Column("changelog", sa.Text(), server_default=""),
        sa.Column("language", sa.Text(), server_default=""),
        sa.Column("framework", sa.Text(), server_default=""),
        sa.Column("dependence_file_name", sa.Text(), server_default=""),
        sa.Column("main_file", sa.Text(), server_default=""),
        sa.Column("diff", sa.Text(), server_default=""),
        sa.Column("commits", sa.Text(), server_default=""),
        sa.Column("source", sa.String(), server_default="local"),
        sa.Column("github_repo", sa.Text(), server_default=""),
        sa.Column("extra", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "llm_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("data", postgresql.JSONB(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_table("llm_config")
    op.drop_table("projects")
    op.drop_table("default_prompts")
    op.drop_table("prompts")
