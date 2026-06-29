from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from app.database import get_db
from app.models import ImportedTrade

router = APIRouter(tags=["trade-ops"])

OPTION_MULTIPLIER = 100


class ClosePositionIn(BaseModel):
    symbol: str
    asset_category: str
    close_price: float
    close_date: str
    quantity: float


class EditPositionIn(BaseModel):
    quantity: float | None = None
    trade_price: float | None = None


@router.post("/trades/close-position")
async def close_position(data: ClosePositionIn, db: AsyncSession = Depends(get_db)):
    mult = OPTION_MULTIPLIER if data.asset_category == "Equity and Index Options" else 1
    closing_qty = -data.quantity

    side_filter = ImportedTrade.quantity > 0 if data.quantity > 0 else ImportedTrade.quantity < 0
    avg_q = select(
        func.sum(ImportedTrade.quantity * ImportedTrade.trade_price) / func.sum(ImportedTrade.quantity)
    ).where(ImportedTrade.symbol == data.symbol, side_filter)
    avg_result = await db.execute(avg_q)
    avg_price = avg_result.scalar_one_or_none() or data.close_price

    if data.quantity > 0:
        pnl = (data.close_price - avg_price) * abs(data.quantity) * mult
    else:
        pnl = (avg_price - data.close_price) * abs(data.quantity) * mult

    sample = await db.execute(select(ImportedTrade).where(ImportedTrade.symbol == data.symbol).limit(1))
    sample_trade = sample.scalar_one_or_none()
    account_id = sample_trade.account_id if sample_trade else "MANUAL"

    trade = ImportedTrade(
        account_id=account_id,
        asset_category=data.asset_category,
        currency="USD",
        symbol=data.symbol,
        date_time=datetime.strptime(data.close_date, "%Y-%m-%d").replace(tzinfo=timezone.utc),
        quantity=closing_qty,
        trade_price=data.close_price,
        proceeds=data.close_price * abs(closing_qty) * mult * (1 if closing_qty < 0 else -1),
        commission=0,
        realized_pnl=round(pnl, 2),
        mtm_pnl=0,
        code="C",
    )
    db.add(trade)
    await db.commit()
    return {"status": "ok", "realized_pnl": round(pnl, 2)}


@router.delete("/trades/by-symbol/{symbol}")
async def delete_by_symbol(symbol: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(delete(ImportedTrade).where(ImportedTrade.symbol == symbol))
    await db.commit()
    return {"status": "ok", "deleted": result.rowcount}


@router.patch("/imported-trades/{trade_id}")
async def update_trade(trade_id: int, data: EditPositionIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ImportedTrade).where(ImportedTrade.id == trade_id))
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    if data.quantity is not None:
        trade.quantity = data.quantity
    if data.trade_price is not None:
        trade.trade_price = data.trade_price

    await db.commit()
    return {"status": "ok"}
