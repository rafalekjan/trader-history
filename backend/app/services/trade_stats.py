"""Trade classification and P&L statistics shared across routers.

IBKR semantics this module encodes:
- The "code" column holds ";"-separated flags: "C" marks a closing trade,
  "P" a partial fill of a close.
- realized_pnl already includes commissions on both legs: the opening fee
  is baked into `basis`, the closing fee into `commission`.
"""
from typing import Iterable

from app.constants import contract_multiplier
from app.models import ImportedTrade

# SQL filters (SQLAlchemy expressions) for query-side classification.
IS_CLOSING = ImportedTrade.code.regexp_match(r"(^|;)C(;|$)")
HAS_PNL = ImportedTrade.realized_pnl != 0


def is_closing(trade: ImportedTrade) -> bool:
    """Python-side counterpart of IS_CLOSING; also catches rows that realized
    P&L without a "C" code (e.g. expirations)."""
    return "C" in trade.code.split(";") or trade.realized_pnl != 0


def trade_status(trade: ImportedTrade) -> str:
    """OPEN / TRIM / WIN / LOSS for a single trade row."""
    if not is_closing(trade):
        return "OPEN"
    codes = trade.code.split(";")
    # A partial close ("C" + "P") is a trim rather than a full win/loss exit.
    if "C" in codes and "P" in codes:
        return "TRIM"
    return "WIN" if trade.realized_pnl >= 0 else "LOSS"


def effective_entry_price(trade: ImportedTrade) -> float | None:
    """Average entry price recovered from IBKR basis (includes opening fees)."""
    if trade.basis is None or not trade.quantity:
        return None
    mult = contract_multiplier(trade.asset_category)
    return round(abs(trade.basis) / (abs(trade.quantity) * mult), 4)


def gross_profit_loss(pnls: Iterable[float]) -> tuple[float, float]:
    """(gross profit, absolute gross loss) over per-trade P&L values."""
    values = list(pnls)
    return (
        sum(p for p in values if p > 0),
        abs(sum(p for p in values if p < 0)),
    )


def profit_factor(gross_profit: float, gross_loss: float) -> float | None:
    """Gross profit / gross loss; None = undefined (profits but no losses, i.e. infinite)."""
    if gross_loss > 0:
        return round(gross_profit / gross_loss, 2)
    return None if gross_profit > 0 else 0.0


def win_rate(wins: int, total: int) -> float:
    """Percentage of winning trades, 0 when there are no trades."""
    return round(wins / total * 100, 1) if total else 0
