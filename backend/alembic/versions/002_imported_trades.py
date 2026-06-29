"""add imported_trades table

Revision ID: 002
Revises: 001
Create Date: 2026-06-29
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "imported_trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.String(50), nullable=False),
        sa.Column("asset_category", sa.String(50), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("symbol", sa.String(100), nullable=False),
        sa.Column("date_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("trade_price", sa.Float(), nullable=False),
        sa.Column("close_price", sa.Float(), nullable=True),
        sa.Column("proceeds", sa.Float(), default=0),
        sa.Column("commission", sa.Float(), default=0),
        sa.Column("basis", sa.Float(), nullable=True),
        sa.Column("realized_pnl", sa.Float(), default=0),
        sa.Column("mtm_pnl", sa.Float(), default=0),
        sa.Column("code", sa.String(50), default=""),
        sa.UniqueConstraint(
            "asset_category", "symbol", "date_time", "quantity", "trade_price", "proceeds",
            name="uq_imported_trade",
        ),
    )
    op.create_index("ix_imported_trades_date", "imported_trades", ["date_time"])
    op.create_index("ix_imported_trades_symbol", "imported_trades", ["symbol"])


def downgrade() -> None:
    op.drop_table("imported_trades")
