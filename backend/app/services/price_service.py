import re
import httpx
from datetime import datetime, timezone

_cache: dict[str, dict] = {}

MONTHS = {
    "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04", "MAY": "05", "JUN": "06",
    "JUL": "07", "AUG": "08", "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
}

YAHOO_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _parse_option_symbol(symbol: str) -> tuple[str, str] | None:
    m = re.match(r"^(.+?)\s+(\d{2})([A-Z]{3})(\d{2})\s+([\d.]+)\s+([CP])$", symbol)
    if not m:
        return None
    ticker, day, mon, year, strike, opt_type = m.groups()
    month = MONTHS.get(mon, "01")
    yahoo_ticker = ticker.replace(" ", "-")
    strike_padded = f"{int(float(strike) * 1000):08d}"
    occ = f"{yahoo_ticker}{year}{month}{day}{opt_type}{strike_padded}"
    return occ, yahoo_ticker


def _fetch_price_yahoo(symbol: str) -> float | None:
    try:
        with httpx.Client(timeout=10, headers=HEADERS) as client:
            r = client.get(YAHOO_URL.format(symbol=symbol), params={"interval": "1d", "range": "5d"})
            if r.status_code != 200:
                return None
            data = r.json()
            result = data.get("chart", {}).get("result")
            if not result:
                return None
            meta = result[0].get("meta", {})
            price = meta.get("regularMarketPrice", 0)
            if price and price > 0:
                return float(price)
    except Exception as e:
        print(f"[prices] fetch error {symbol}: {e}")
    return None


def refresh_prices(symbols: list[tuple[str, str]]) -> dict[str, dict]:
    now = datetime.now(timezone.utc).isoformat()
    updated: dict[str, dict] = {}

    for sym, cat in symbols:
        price = None

        if cat == "Stocks":
            yahoo = sym.replace(" ", "-")
            price = _fetch_price_yahoo(yahoo)
        else:
            parsed = _parse_option_symbol(sym)
            if parsed:
                occ, underlying = parsed
                price = _fetch_price_yahoo(occ)
                if price is None:
                    price = _fetch_price_yahoo(underlying)

        if price is not None:
            entry = {"price": price, "updated_at": now}
            _cache[sym] = entry
            updated[sym] = entry

    return updated


def get_cached() -> dict[str, dict]:
    return dict(_cache)


def get_price(symbol: str) -> float | None:
    entry = _cache.get(symbol)
    return entry["price"] if entry else None


def get_last_updated() -> str | None:
    if not _cache:
        return None
    return max(e["updated_at"] for e in _cache.values())
