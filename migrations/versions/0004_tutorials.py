"""tutorial categories and tutorials

Revision ID: 0004_tutorials
Revises: 0003_user_subscriptions
Create Date: 2026-02-26

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_tutorials"
down_revision = "0003_user_subscriptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tutorial_categories",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tutorial_categories_slug", "tutorial_categories", ["slug"], unique=True)

    op.create_table(
        "tutorials",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("category_id", sa.String(length=36), sa.ForeignKey("tutorial_categories.id"), nullable=False),
        sa.Column("slug", sa.String(length=96), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("required_plan", sa.String(length=32), nullable=False, server_default="free"),
        sa.Column("video_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("file_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tutorials_category_id", "tutorials", ["category_id"])
    op.create_index("ix_tutorials_slug", "tutorials", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_tutorials_slug", table_name="tutorials")
    op.drop_index("ix_tutorials_category_id", table_name="tutorials")
    op.drop_table("tutorials")

    op.drop_index("ix_tutorial_categories_slug", table_name="tutorial_categories")
    op.drop_table("tutorial_categories")
