"""add overdue_escalation_sent_at to tasks

Revision ID: d8e3b1c0a4f2
Revises: c4f91a2b8e10
Create Date: 2026-04-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8e3b1c0a4f2"
down_revision: Union[str, Sequence[str], None] = "c4f91a2b8e10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("overdue_escalation_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tasks", "overdue_escalation_sent_at")
