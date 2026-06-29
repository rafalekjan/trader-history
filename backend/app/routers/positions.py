from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Position
from app.schemas import PositionOut

router = APIRouter(tags=["positions"])


@router.get("/positions", response_model=list[PositionOut])
async def get_positions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Position))
    return result.scalars().all()
