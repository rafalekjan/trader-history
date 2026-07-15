"""Trade listing and manual trade operations (close / delete)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, delete, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import OPTION_CATEGORY, contract_multiplier
from app.database import get_db
from app.models import ImportedTrade
from app.schemas import ClosePositionIn, ImportedTradeOut

router = APIRouter(tags=["trades"])

# Filter values accepted by the trade_type query param -> stored asset_category.
ASSET_MAP = {"Stock": "Stocks", "Option": OPTION_CATEGORY, "Future": "Futures"}


@router.get("/imported-trades", response_model=list[ImportedTradeOut])
async def get_imported_trades(
    limit: int = Query(200, le=2000),
    offset: int = Query(0, ge=0),
    search: str | None = None,
    side: str | None = Query(None, pattern="^(long|short)$"),
    trade_type: str | None = None,
    sort_by: str = Query("date", pattern="^(date|pnl)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
):
    q = select(ImportedTrade)
    if search:
        q = q.where(ImportedTrade.symbol.ilike(f"%{search}%"))
    if side:
        q = q.where(ImportedTrade.quantity > 0 if side == "long" else ImportedTrade.quantity < 0)
    if trade_type in ASSET_MAP:
        q = q.where(ImportedTrade.asset_category == ASSET_MAP[trade_type])

    order_col = ImportedTrade.date_time if sort_by == "date" else ImportedTrade.realized_pnl
    q = q.order_by(desc(order_col) if sort_dir == "desc" else asc(order_col))

    result = await db.execute(q.limit(limit).offset(offset))
    return result.scalars().all()


@router.post("/trades/close-position")
async def close_position(data: ClosePositionIn, db: AsyncSession = Depends(get_db)):
    """Record a manual closing trade for an open position and its realized P&L."""
    mult = contract_multiplier(data.asset_category)
    is_long = data.quantity > 0
    closing_qty = -data.quantity  # opposite side to flatten the position

    # Average entry price from the opening trades on the same side.
    side_filter = ImportedTrade.quantity > 0 if is_long else ImportedTrade.quantity < 0
    avg_result = await db.execute(
        select(func.sum(ImportedTrade.quantity * ImportedTrade.trade_price) / func.sum(ImportedTrade.quantity))
        .where(ImportedTrade.symbol == data.symbol, side_filter)
    )
    avg_price = avg_result.scalar_one_or_none() or data.close_price

    price_diff = data.close_price - avg_price if is_long else avg_price - data.close_price
    pnl = round(price_diff * abs(data.quantity) * mult, 2)

    sample = await db.execute(select(ImportedTrade).where(ImportedTrade.symbol == data.symbol).limit(1))
    sample_trade = sample.scalar_one_or_none()

    db.add(ImportedTrade(
        account_id=sample_trade.account_id if sample_trade else "MANUAL",
        asset_category=data.asset_category,
        currency="USD",
        symbol=data.symbol,
        date_time=datetime.strptime(data.close_date, "%Y-%m-%d").replace(tzinfo=timezone.utc),
        quantity=closing_qty,
        trade_price=data.close_price,
        proceeds=data.close_price * abs(closing_qty) * mult * (1 if closing_qty < 0 else -1),
        commission=0,
        realized_pnl=pnl,
        mtm_pnl=0,
        code="C",
    ))
    await db.commit()
    return {"status": "ok", "realized_pnl": pnl}


@router.delete("/trades/by-symbol/{symbol}")
async def delete_by_symbol(symbol: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(delete(ImportedTrade).where(ImportedTrade.symbol == symbol))
    await db.commit()
    return {"status": "ok", "deleted": result.rowcount}
