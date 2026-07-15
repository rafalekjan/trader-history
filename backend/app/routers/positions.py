"""Open positions and the live price feed."""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import contract_multiplier
from app.database import get_db, async_session
from app.models import ImportedTrade
from app.schemas import OpenPositionOut
from app.services import price_service

router = APIRouter(tags=["positions"])


async def fetch_open_symbols() -> list[tuple[str, str]]:
    """(symbol, asset_category) pairs for every position with a non-zero net quantity."""
    async with async_session() as db:
        result = await db.execute(
            select(ImportedTrade.symbol, ImportedTrade.asset_category)
            .group_by(ImportedTrade.symbol, ImportedTrade.asset_category)
            .having(func.sum(ImportedTrade.quantity) != 0)
        )
        return [(r.symbol, r.asset_category) for r in result.all()]


@router.get("/analytics/open-positions", response_model=list[OpenPositionOut])
async def get_open_positions(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(
            ImportedTrade.symbol,
            ImportedTrade.asset_category,
            func.sum(ImportedTrade.quantity).label("net_qty"),
            func.sum(ImportedTrade.quantity * ImportedTrade.trade_price).label("total_cost"),
        )
        .group_by(ImportedTrade.symbol, ImportedTrade.asset_category)
        .having(func.sum(ImportedTrade.quantity) != 0)
    )).all()

    # For symbols without a live quote, fall back to the most recent
    # close_price from the imported statement (one DISTINCT ON query).
    missing = [r.symbol for r in rows if price_service.get_price(r.symbol) is None]
    fallback: dict[str, float] = {}
    if missing:
        fb_rows = (await db.execute(
            select(ImportedTrade.symbol, ImportedTrade.close_price)
            .where(ImportedTrade.symbol.in_(missing), ImportedTrade.close_price.isnot(None))
            .distinct(ImportedTrade.symbol)
            .order_by(ImportedTrade.symbol, desc(ImportedTrade.date_time))
        )).all()
        fallback = {r.symbol: float(r.close_price) for r in fb_rows}

    positions = []
    for row in rows:
        qty = float(row.net_qty)
        cost = float(row.total_cost)
        mult = contract_multiplier(row.asset_category)
        avg = abs(cost / qty) if qty else 0
        price = price_service.get_price(row.symbol) or fallback.get(row.symbol)

        positions.append(OpenPositionOut(
            symbol=row.symbol,
            asset_category=row.asset_category,
            quantity=round(qty, 4),
            avg_price=round(avg, 4),
            market_value=round(abs(cost) * mult, 2),
            current_price=round(price, 4) if price is not None else None,
            unrealized_pnl=round((price - avg) * qty * mult, 2) if price is not None else None,
        ))
    return positions


@router.get("/analytics/prices")
async def get_prices():
    return {"prices": price_service.get_cached(), "last_updated": price_service.get_last_updated()}


@router.post("/analytics/prices/refresh")
async def refresh_prices_now():
    symbols = await fetch_open_symbols()
    if not symbols:
        return {"status": "ok", "updated": 0, "last_updated": None}
    updated = await price_service.refresh_prices(symbols)
    return {"status": "ok", "updated": len(updated), "last_updated": price_service.get_last_updated()}
