"""site content

Revision ID: 0002_site_content
Revises: 0001_init
Create Date: 2026-02-26

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_site_content"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_content",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("founder_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("founder_intro", sa.Text(), nullable=False, server_default=""),
        sa.Column("founder_photo_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("founder_video_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.execute(
        sa.text(
            """
            INSERT INTO site_content (id, founder_name, founder_intro, founder_photo_url, founder_video_url, updated_at)
            VALUES (
                1,
                'Founder',
                'I built this protocol to make practical longevity guidance simple and measurable.',
                '',
                '',
                NOW()
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_table("site_content")
