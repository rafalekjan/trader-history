"""Live price feed backed by the public Yahoo Finance chart API.

Prices are fetched concurrently and kept in an in-process cache; the
background loop in `app.main` refreshes them every few minutes. The same
cache also holds FX rates (e.g. PLNUSD=X) used for deposit conversion.
"""
import asyncio
import logging
import re
from datetime import datetime, timezone

import httpx

logger = logging.getLogger("prices")

YAHOO_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
MAX_CONCURRENCY = 8

# Fallback used when the live PLNUSD=X quote has not been fetched yet.
DEFAULT_FX_USD = {"PLN": 0.2768}

MONTHS = {
    "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04", "MAY": "05", "JUN": "06",
    "JUL": "07", "AUG": "08", "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
}

# IBKR option symbol, e.g. "ABNB 17JUL26 150 C"
OPTION_RE = re.compile(r"^(.+?)\s+(\d{2})([A-Z]{3})(\d{2})\s+([\d.]+)\s+([CP])$")

_cache: dict[str, dict] = {}
_fx_cache: dict[str, float] = {}


def _to_occ_symbol(symbol: str) -> tuple[str, str] | None:
    """Convert an IBKR option symbol to (OCC contract symbol, underlying ticker)."""
    m = OPTION_RE.match(symbol)
    if not m:
        return None
    ticker, day, mon, year, strike, opt_type = m.groups()
    underlying = ticker.replace(" ", "-")
    strike_padded = f"{int(float(strike) * 1000):08d}"
    return f"{underlying}{year}{MONTHS.get(mon, '01')}{day}{opt_type}{strike_padded}", underlying


async def _fetch_quote(client: httpx.AsyncClient, symbol: str) -> float | None:
    try:
        r = await client.get(YAHOO_URL.format(symbol=symbol), params={"interval": "1d", "range": "5d"})
        if r.status_code != 200:
            return None
        result = r.json().get("chart", {}).get("result")
        if not result:
            return None
        price = result[0].get("meta", {}).get("regularMarketPrice")
        return float(price) if price and price > 0 else None
    except Exception as e:
        logger.warning("fetch failed for %s: %s", symbol, e)
        return None


async def _resolve_price(client: httpx.AsyncClient, symbol: str, category: str) -> float | None:
    if category == "Stocks":
        return await _fetch_quote(client, symbol.replace(" ", "-"))

    parsed = _to_occ_symbol(symbol)
    if not parsed:
        return None
    occ, underlying = parsed
    # OCC contract quote first; fall back to the underlying if unavailable.
    return await _fetch_quote(client, occ) or await _fetch_quote(client, underlying)


async def refresh_prices(symbols: list[tuple[str, str]]) -> dict[str, dict]:
    """Fetch quotes for all symbols concurrently and update the cache."""
    now = datetime.now(timezone.utc).isoformat()
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:

        async def fetch_one(sym: str, cat: str) -> tuple[str, float | None]:
            async with semaphore:
                return sym, await _resolve_price(client, sym, cat)

        results = await asyncio.gather(*(fetch_one(s, c) for s, c in symbols))

        fx = await _fetch_quote(client, "PLNUSD=X")
        if fx:
            _fx_cache["PLN"] = fx

    updated: dict[str, dict] = {}
    for sym, price in results:
        if price is not None:
            entry = {"price": price, "updated_at": now}
            _cache[sym] = entry
            updated[sym] = entry
    return updated


def get_price(symbol: str) -> float | None:
    entry = _cache.get(symbol)
    return entry["price"] if entry else None


def get_cached() -> dict[str, dict]:
    return dict(_cache)


def get_last_updated() -> str | None:
    return max((e["updated_at"] for e in _cache.values()), default=None)


def get_fx_usd_rate(currency: str) -> float:
    """USD value of one unit of `currency` (1.0 for USD itself)."""
    if currency == "USD":
        return 1.0
    return _fx_cache.get(currency) or DEFAULT_FX_USD.get(currency, 0.0)
