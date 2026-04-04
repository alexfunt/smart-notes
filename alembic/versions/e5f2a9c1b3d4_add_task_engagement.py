"""add engagement_score and reminder engagement timestamps

Revision ID: e5f2a9c1b3d4
Revises: d8e3b1c0a4f2
Create Date: 2026-04-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f2a9c1b3d4"
down_revision: Union[str, Sequence[str], None] = "d8e3b1c0a4f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("engagement_score", sa.Float(), nullable=False, server_default="0.5"),
    )
    op.add_column(
        "tasks",
        sa.Column("last_user_engagement_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("last_reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE tasks SET last_user_engagement_at = COALESCE(updated_at, created_at) "
        "WHERE last_user_engagement_at IS NULL"
    )
    op.alter_column(
        "tasks",
        "last_user_engagement_at",
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("tasks", "last_reminder_sent_at")
    op.drop_column("tasks", "last_user_engagement_at")
    op.drop_column("tasks", "engagement_score")
