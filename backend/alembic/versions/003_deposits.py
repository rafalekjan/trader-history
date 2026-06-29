"""add deposits table

Revision ID: 003
Revises: 002
Create Date: 2026-06-29
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "imported_deposits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.String(50), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("settle_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.UniqueConstraint("account_id", "currency", "settle_date", "description", "amount", name="uq_deposit"),
    )


def downgrade() -> None:
    op.drop_table("imported_deposits")
