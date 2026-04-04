"""add last_reminder_telegram_message_id to tasks

Revision ID: c4f91a2b8e10
Revises: 09f579c2470f
Create Date: 2026-04-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4f91a2b8e10"
down_revision: Union[str, Sequence[str], None] = "09f579c2470f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("last_reminder_telegram_message_id", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tasks", "last_reminder_telegram_message_id")
