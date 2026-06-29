from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.database import get_db
from app.models import Trade, Position, Balance
from app.schemas import ImportResult
from app.services.ibkr_client import get_ibkr_client

router = APIRouter(tags=["import"])


@router.post("/import/trades", response_model=ImportResult)
async def import_trades(db: AsyncSession = Depends(get_db)):
    try:
        client = await get_ibkr_client(db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        raw_trades = await client.get_trades()
    finally:
        await client.close()

    count = 0
    for t in raw_trades:
        trade_time = t.get("trade_time_r")
        if trade_time:
            trade_time = datetime.fromtimestamp(trade_time / 1000, tz=timezone.utc)
        else:
            trade_time = datetime.now(timezone.utc)

        stmt = pg_insert(Trade).values(
            account_id=t.get("account", ""),
            conid=t.get("conid"),
            symbol=t.get("symbol", ""),
            side=t.get("side", ""),
            quantity=float(t.get("size", 0)),
            price=float(t.get("price", 0)),
            commission=float(t.get("commission", 0)),
            trade_time=trade_time,
            order_ref=t.get("order_ref", ""),
            exchange=t.get("exchange", ""),
            raw_data=t,
        ).on_conflict_do_nothing(constraint="uq_trade")
        await db.execute(stmt)
        count += 1

    await db.commit()
    return ImportResult(status="ok", imported=count, message=f"Imported {count} trades")


@router.post("/import/positions", response_model=ImportResult)
async def import_positions(db: AsyncSession = Depends(get_db)):
    try:
        client = await get_ibkr_client(db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        raw_positions = await client.get_positions()
    finally:
        await client.close()

    count = 0
    for p in raw_positions:
        stmt = pg_insert(Position).values(
            account_id=p.get("acctId", ""),
            conid=p.get("conid"),
            symbol=p.get("contractDesc", ""),
            quantity=float(p.get("position", 0)),
            avg_cost=float(p.get("avgCost", 0)),
            market_value=float(p.get("mktValue", 0)),
            unrealized_pnl=float(p.get("unrealizedPnl", 0)),
            raw_data=p,
        ).on_conflict_do_update(
            constraint="uq_position",
            set_={
                "quantity": float(p.get("position", 0)),
                "avg_cost": float(p.get("avgCost", 0)),
                "market_value": float(p.get("mktValue", 0)),
                "unrealized_pnl": float(p.get("unrealizedPnl", 0)),
                "raw_data": p,
            },
        )
        await db.execute(stmt)
        count += 1

    await db.commit()
    return ImportResult(status="ok", imported=count, message=f"Imported {count} positions")


@router.post("/import/balances", response_model=ImportResult)
async def import_balances(db: AsyncSession = Depends(get_db)):
    try:
        client = await get_ibkr_client(db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        summary = await client.get_account_summary()
    finally:
        await client.close()

    balance = Balance(
        account_id=summary.get("accountId", ""),
        currency=summary.get("currency", "USD"),
        total_cash=float(summary.get("totalcashvalue", {}).get("amount", 0)),
        net_liquidation=float(summary.get("netliquidation", {}).get("amount", 0)),
        equity_with_loan=float(summary.get("equitywithloanvalue", {}).get("amount", 0)),
        margin_used=float(summary.get("initmarginreq", {}).get("amount", 0)),
        raw_data=summary,
    )
    db.add(balance)
    await db.commit()

    return ImportResult(status="ok", imported=1, message="Balance snapshot saved")
