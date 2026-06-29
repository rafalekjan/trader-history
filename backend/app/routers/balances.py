from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database import get_db
from app.models import Balance
from app.schemas import BalanceOut

router = APIRouter(tags=["balances"])


@router.get("/balances", response_model=list[BalanceOut])
async def get_balances(
    limit: int = Query(50, le=500),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Balance).order_by(desc(Balance.snapshot_time)).limit(limit)
    )
    return result.scalars().all()
