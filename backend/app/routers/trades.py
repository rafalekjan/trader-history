from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database import get_db
from app.models import Trade
from app.schemas import TradeOut

router = APIRouter(tags=["trades"])


@router.get("/trades", response_model=list[TradeOut])
async def get_trades(
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Trade).order_by(desc(Trade.trade_time)).limit(limit).offset(offset)
    )
    return result.scalars().all()
