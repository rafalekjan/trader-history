"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-29
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(255), unique=True, nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("is_encrypted", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.String(50), nullable=False),
        sa.Column("conid", sa.Integer(), nullable=True),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("commission", sa.Float(), default=0),
        sa.Column("trade_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("order_ref", sa.String(100), nullable=True),
        sa.Column("exchange", sa.String(50), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint("account_id", "order_ref", "trade_time", name="uq_trade"),
    )

    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.String(50), nullable=False),
        sa.Column("conid", sa.Integer(), nullable=True),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("avg_cost", sa.Float(), nullable=False),
        sa.Column("market_value", sa.Float(), default=0),
        sa.Column("unrealized_pnl", sa.Float(), default=0),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("raw_data", postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint("account_id", "symbol", name="uq_position"),
    )

    op.create_table(
        "balances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.String(50), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("total_cash", sa.Float(), default=0),
        sa.Column("net_liquidation", sa.Float(), default=0),
        sa.Column("equity_with_loan", sa.Float(), default=0),
        sa.Column("margin_used", sa.Float(), default=0),
        sa.Column("snapshot_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("raw_data", postgresql.JSONB(), nullable=True),
    )

    op.create_table(
        "price_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conid", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), default=0),
        sa.UniqueConstraint("conid", "date", name="uq_price_history"),
    )


def downgrade() -> None:
    op.drop_table("price_history")
    op.drop_table("balances")
    op.drop_table("positions")
    op.drop_table("trades")
    op.drop_table("settings")
