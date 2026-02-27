"""add user profile fields

Revision ID: 0005_user_profile_fields
Revises: 0004_tutorials
Create Date: 2026-02-27

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_user_profile_fields"
down_revision = "0004_tutorials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("first_name", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(length=100), nullable=True))
    op.create_index("ix_users_username", "users", ["username"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
    op.drop_column("users", "username")
