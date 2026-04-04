"""add next_check_at to task

Revision ID: 09f579c2470f
Revises: 548d5d62ff53
Create Date: 2026-04-03 22:53:00.421832

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '09f579c2470f'
down_revision: Union[str, Sequence[str], None] = '548d5d62ff53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tasks", "next_check_at")
