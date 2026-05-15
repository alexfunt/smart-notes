"""add note focus_score for topic attention (noise reduction ordering)

Revision ID: f1a2b3c4d5e6
Revises: e5f2a9c1b3d4
Create Date: 2026-04-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e5f2a9c1b3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notes",
        sa.Column("focus_score", sa.Float(), nullable=False, server_default="0.5"),
    )
    op.add_column(
        "notes",
        sa.Column("last_focus_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notes", "last_focus_at")
    op.drop_column("notes", "focus_score")
