"""Parser for IBKR Activity Statement CSV exports.

The statement is a bundle of sections in one file; each row names its section
in column 0. Only "Account Information", "Trades" and "Deposits & Withdrawals"
are consumed here — malformed rows are skipped rather than failing the import.
"""
import csv
import io
from dataclasses import dataclass, field
from datetime import datetime, timezone, date


@dataclass
class ParsedStatement:
    account_id: str = ""
    trades: list[dict] = field(default_factory=list)
    deposits: list[dict] = field(default_factory=list)


def _parse_deposit_row(row: list[str]) -> dict | None:
    currency = row[2].strip()
    # Skip aggregate/total rows; keep only per-currency deposit lines.
    if currency in ("Total", "Total in USD", ""):
        return None
    try:
        return {
            "currency": currency,
            "settle_date": date.fromisoformat(row[3].strip()),
            "description": row[4].strip(),
            "amount": float(row[5].strip()),
        }
    except (ValueError, IndexError):
        return None


def _parse_trade_row(row: list[str]) -> dict | None:
    asset_category = row[3].strip()
    if "Forex" in asset_category:
        return None
    try:
        close_price = None
        cp = row[9].strip()
        if cp and cp != "--":
            close_price = float(cp)

        basis = None
        b = row[12].strip()
        if b:
            basis = float(b)

        return {
            "asset_category": asset_category,
            "currency": row[4].strip(),
            "symbol": row[5].strip(),
            "date_time": datetime.strptime(row[6].strip(), "%Y-%m-%d, %H:%M:%S").replace(tzinfo=timezone.utc),
            "quantity": float(row[7]),
            "trade_price": float(row[8]),
            "close_price": close_price,
            "proceeds": float(row[10]),
            "commission": float(row[11]),
            "basis": basis,
            "realized_pnl": float(row[13]) if row[13].strip() else 0,
            "mtm_pnl": float(row[14]) if row[14].strip() else 0,
            "code": row[15].strip() if len(row) > 15 else "",
        }
    except (ValueError, IndexError):
        return None


def parse_ibkr_csv(content: str) -> ParsedStatement:
    parsed = ParsedStatement()
    reader = csv.reader(io.StringIO(content.lstrip("﻿")))

    for row in reader:
        if len(row) >= 4 and row[0] == "Account Information" and row[2] == "Account":
            parsed.account_id = row[3].strip()
        elif len(row) >= 6 and row[0] == "Deposits & Withdrawals" and row[1] == "Data":
            if (deposit := _parse_deposit_row(row)) is not None:
                parsed.deposits.append(deposit)
        elif len(row) >= 15 and row[0] == "Trades" and row[1] == "Data" and row[2] == "Order":
            if (trade := _parse_trade_row(row)) is not None:
                parsed.trades.append(trade)

    return parsed
