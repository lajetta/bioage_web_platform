"""add user password hash

Revision ID: 0006_user_password_hash
Revises: 0005_user_profile_fields
Create Date: 2026-02-27

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_user_password_hash"
down_revision = "0005_user_profile_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
