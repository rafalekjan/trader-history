import csv
import io
from datetime import datetime, timezone, date


def parse_ibkr_csv(content: str) -> dict:
    account_id = ""
    trades: list[dict] = []
    deposits: list[dict] = []
    total_deposits_usd = 0.0

    content = content.lstrip("﻿")
    reader = csv.reader(io.StringIO(content))

    for row in reader:
        if len(row) >= 4 and row[0] == "Account Information" and row[2] == "Account":
            account_id = row[3].strip()
            continue

        if len(row) >= 6 and row[0] == "Deposits & Withdrawals" and row[1] == "Data":
            cur = row[2].strip()
            if cur == "Total in USD":
                try:
                    total_deposits_usd = float(row[5].strip())
                except (ValueError, IndexError):
                    pass
                continue
            if cur in ("Total", ""):
                continue
            try:
                deposits.append({
                    "currency": cur,
                    "settle_date": date.fromisoformat(row[3].strip()),
                    "description": row[4].strip(),
                    "amount": float(row[5].strip()),
                })
            except (ValueError, IndexError):
                continue
            continue

        if len(row) < 15:
            continue
        if row[0] != "Trades" or row[1] != "Data" or row[2] != "Order":
            continue

        asset_category = row[3].strip()
        if "Forex" in asset_category:
            continue

        try:
            close_price = None
            cp = row[9].strip()
            if cp and cp != "--":
                close_price = float(cp)

            basis = None
            b = row[12].strip()
            if b:
                basis = float(b)

            trades.append({
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
            })
        except (ValueError, IndexError):
            continue

    return {
        "account_id": account_id,
        "trades": trades,
        "deposits": deposits,
        "total_deposits_usd": total_deposits_usd,
    }
