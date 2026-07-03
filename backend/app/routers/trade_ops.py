from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from app.database import get_db
from app.models import ImportedTrade
from app.constants import contract_multiplier

router = APIRouter(tags=["trade-ops"])


class ClosePositionIn(BaseModel):
    symbol: str
    asset_category: str
    close_price: float
    close_date: str
    quantity: float  # signed net position (+ long, - short)


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
