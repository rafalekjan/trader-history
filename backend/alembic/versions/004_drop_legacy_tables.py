"""drop legacy IBKR-API tables (settings, trades, positions, balances, price_history)

Revision ID: 004
Revises: 003
Create Date: 2026-06-29
"""
from typing import Sequence, Union
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LEGACY_TABLES = ["settings", "trades", "positions", "balances", "price_history"]


def upgrade() -> None:
    for table in LEGACY_TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')


def downgrade() -> None:
    # Legacy tables from the abandoned IBKR-API design; not recreated on downgrade.
    pass
