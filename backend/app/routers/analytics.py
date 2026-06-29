import asyncio
from collections import defaultdict
from datetime import date as date_type
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc, or_, cast, Date
from app.database import get_db, async_session
from app.models import ImportedTrade, ImportedDeposit
from app.schemas import (
    ImportedTradeOut, MonthlyStats, DailyPnL, CumulativePnLPoint,
    TradeSummary, DayDetail, DayTradeEntry, OpenPositionOut,
    FullStats, TradeRef, DepositsResponse, DepositOut,
)
from app.services import price_service

router = APIRouter(tags=["analytics"])

CLOSING_EXPR = or_(
    ImportedTrade.code == "C",
    ImportedTrade.code.like("C;%"),
    ImportedTrade.code.like("%;C"),
    ImportedTrade.code.like("%;C;%"),
)

ASSET_MAP = {"Stock": "Stocks", "Option": "Equity and Index Options", "Future": "Futures"}


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
    if side == "long":
        q = q.where(ImportedTrade.quantity > 0)
    elif side == "short":
        q = q.where(ImportedTrade.quantity < 0)
    if trade_type and trade_type in ASSET_MAP:
        q = q.where(ImportedTrade.asset_category == ASSET_MAP[trade_type])

    order_col = ImportedTrade.date_time if sort_by == "date" else ImportedTrade.realized_pnl
    q = q.order_by(desc(order_col) if sort_dir == "desc" else asc(order_col))
    q = q.limit(limit).offset(offset)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/analytics/summary", response_model=TradeSummary)
async def get_summary(db: AsyncSession = Depends(get_db)):
    pnl_r = await db.execute(select(func.coalesce(func.sum(ImportedTrade.realized_pnl), 0)))
    net_pnl = float(pnl_r.scalar_one())

    open_r = await db.execute(
        select(func.count()).select_from(
            select(ImportedTrade.symbol).group_by(ImportedTrade.symbol)
            .having(func.sum(ImportedTrade.quantity) != 0).subquery()
        )
    )
    open_trades = int(open_r.scalar_one())

    logged_r = await db.execute(select(func.count()).where(CLOSING_EXPR))
    logged = int(logged_r.scalar_one())

    wins_r = await db.execute(select(func.count()).where(CLOSING_EXPR, ImportedTrade.realized_pnl > 0))
    wins = int(wins_r.scalar_one())

    return TradeSummary(
        net_realized_pnl=round(net_pnl, 2), open_trades=open_trades,
        logged_trades=logged,
        win_rate=round((wins / logged * 100) if logged > 0 else 0, 1),
    )


@router.get("/analytics/open-positions", response_model=list[OpenPositionOut])
async def get_open_positions(db: AsyncSession = Depends(get_db)):
    q = select(
        ImportedTrade.symbol, ImportedTrade.asset_category,
        func.sum(ImportedTrade.quantity).label("net_qty"),
        func.sum(ImportedTrade.quantity * ImportedTrade.trade_price).label("total_cost"),
    ).group_by(ImportedTrade.symbol, ImportedTrade.asset_category
    ).having(func.sum(ImportedTrade.quantity) != 0)

    result = await db.execute(q)
    rows = result.all()

    positions = []
    for row in rows:
        qty = float(row.net_qty)
        cost = float(row.total_cost)
        mult = 100 if row.asset_category == "Equity and Index Options" else 1
        avg = abs(cost / qty) if qty else 0

        live = price_service.get_price(row.symbol)
        if live is None:
            price_q = select(ImportedTrade.close_price).where(
                ImportedTrade.symbol == row.symbol,
                ImportedTrade.close_price.isnot(None),
            ).order_by(desc(ImportedTrade.date_time)).limit(1)
            pr = await db.execute(price_q)
            live = pr.scalar_one_or_none()
            if live is not None:
                live = float(live)

        unrealized = round((live - avg) * qty * mult, 2) if live is not None else None

        positions.append(OpenPositionOut(
            symbol=row.symbol, asset_category=row.asset_category,
            quantity=round(qty, 4), avg_price=round(avg, 4),
            market_value=round(abs(cost) * mult, 2),
            current_price=round(live, 4) if live is not None else None,
            unrealized_pnl=unrealized,
        ))
    return positions


@router.get("/analytics/prices")
async def get_prices():
    cached = price_service.get_cached()
    return {"prices": cached, "last_updated": price_service.get_last_updated()}


@router.post("/analytics/prices/refresh")
async def refresh_prices_now():
    async with async_session() as db:
        q = select(
            ImportedTrade.symbol, ImportedTrade.asset_category,
        ).group_by(ImportedTrade.symbol, ImportedTrade.asset_category
        ).having(func.sum(ImportedTrade.quantity) != 0)
        result = await db.execute(q)
        symbols = [(r.symbol, r.asset_category) for r in result.all()]

    if not symbols:
        return {"status": "ok", "updated": 0}

    updated = await asyncio.to_thread(price_service.refresh_prices, symbols)
    return {"status": "ok", "updated": len(updated), "last_updated": price_service.get_last_updated()}


@router.get("/analytics/day-detail", response_model=DayDetail)
async def get_day_detail(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: AsyncSession = Depends(get_db),
):
    parsed = date_type.fromisoformat(date)
    q = select(ImportedTrade).where(
        cast(ImportedTrade.date_time, Date) == parsed,
        ImportedTrade.realized_pnl != 0,
    ).order_by(desc(ImportedTrade.realized_pnl))

    result = await db.execute(q)
    rows = result.scalars().all()

    wins = losses = trims = 0
    entries: list[DayTradeEntry] = []
    for t in rows:
        codes = t.code.split(";")
        is_trim = "C" in codes and "P" in codes
        if is_trim:
            trims += 1; status = "TRIM"
        elif t.realized_pnl > 0:
            wins += 1; status = "WIN"
        else:
            losses += 1; status = "LOSS"
        entries.append(DayTradeEntry(
            symbol=t.symbol, asset_category=t.asset_category,
            quantity=t.quantity, trade_price=t.trade_price,
            realized_pnl=round(t.realized_pnl, 2), status=status,
        ))

    return DayDetail(
        date=date, realized_pnl=round(sum(t.realized_pnl for t in rows), 2),
        wins=wins, losses=losses, trims=trims, trades=entries,
    )


@router.get("/analytics/stats", response_model=FullStats)
async def get_full_stats(
    start_date: str | None = None,
    end_date: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(ImportedTrade).where(CLOSING_EXPR, ImportedTrade.realized_pnl != 0)
    if start_date:
        q = q.where(cast(ImportedTrade.date_time, Date) >= date_type.fromisoformat(start_date))
    if end_date:
        q = q.where(cast(ImportedTrade.date_time, Date) <= date_type.fromisoformat(end_date))

    result = await db.execute(q)
    closing_trades = result.scalars().all()

    if not closing_trades:
        return FullStats(
            net_realized_pnl=0, win_rate=0, closed_trades=0, profit_factor=0,
            avg_win=0, avg_loss=0, best_trade=None, worst_trade=None,
        )

    wins = [t for t in closing_trades if t.realized_pnl > 0]
    losses_list = [t for t in closing_trades if t.realized_pnl < 0]
    gp = sum(t.realized_pnl for t in wins)
    gl = abs(sum(t.realized_pnl for t in losses_list))
    net = sum(t.realized_pnl for t in closing_trades)
    best = max(closing_trades, key=lambda t: t.realized_pnl)
    worst = min(closing_trades, key=lambda t: t.realized_pnl)

    return FullStats(
        net_realized_pnl=round(net, 2),
        win_rate=round(len(wins) / len(closing_trades) * 100, 1),
        closed_trades=len(closing_trades),
        profit_factor=round(gp / gl, 2) if gl > 0 else round(gp, 2),
        avg_win=round(gp / len(wins), 2) if wins else 0,
        avg_loss=round(-gl / len(losses_list), 2) if losses_list else 0,
        best_trade=TradeRef(symbol=best.symbol, pnl=round(best.realized_pnl, 2), date=str(best.date_time.date())),
        worst_trade=TradeRef(symbol=worst.symbol, pnl=round(worst.realized_pnl, 2), date=str(worst.date_time.date())),
    )


@router.get("/analytics/deposits", response_model=DepositsResponse)
async def get_deposits(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ImportedDeposit).order_by(ImportedDeposit.settle_date))
    deps = result.scalars().all()
    totals: dict[str, float] = defaultdict(float)
    for d in deps:
        totals[d.currency] += d.amount
    usd_from_pln = totals.get("PLN", 0) * 0.2768
    return DepositsResponse(
        deposits=[DepositOut.model_validate(d) for d in deps],
        total_native=dict(totals),
        total_usd=round(totals.get("USD", 0) + usd_from_pln, 2),
    )


@router.get("/analytics/monthly-pnl", response_model=MonthlyStats)
async def get_monthly_pnl(
    year: int = Query(...), month: int = Query(..., ge=1, le=12),
    db: AsyncSession = Depends(get_db),
):
    date_col = func.date(ImportedTrade.date_time)
    q = select(date_col.label("trade_date"), ImportedTrade.realized_pnl).where(
        func.extract("year", ImportedTrade.date_time) == year,
        func.extract("month", ImportedTrade.date_time) == month,
        ImportedTrade.realized_pnl != 0,
    ).order_by(date_col)
    result = await db.execute(q)
    daily_map: dict[str, dict] = defaultdict(lambda: {"pnl": 0.0, "trades": 0, "wins": 0, "losses": 0})
    for row in result.all():
        d = str(row.trade_date)
        daily_map[d]["pnl"] += row.realized_pnl
        daily_map[d]["trades"] += 1
        if row.realized_pnl > 0: daily_map[d]["wins"] += 1
        else: daily_map[d]["losses"] += 1
    daily = [DailyPnL(date=d, pnl=round(v["pnl"], 2), trade_count=v["trades"], wins=v["wins"], losses=v["losses"])
             for d, v in sorted(daily_map.items())]
    tp = sum(d.pnl for d in daily); tt = sum(d.trade_count for d in daily)
    tw = sum(d.wins for d in daily); tl = sum(d.losses for d in daily)
    gp = sum(d.pnl for d in daily if d.pnl > 0); gl = abs(sum(d.pnl for d in daily if d.pnl < 0))
    return MonthlyStats(year=year, month=month, total_pnl=round(tp, 2), trade_count=tt, wins=tw, losses=tl,
        win_rate=round(tw / tt * 100, 1) if tt else 0, profit_factor=round(gp / gl, 2) if gl else round(gp, 2), daily=daily)


@router.get("/analytics/cumulative-pnl", response_model=list[CumulativePnLPoint])
async def get_cumulative_pnl(db: AsyncSession = Depends(get_db)):
    date_col = func.date(ImportedTrade.date_time)
    q = select(date_col.label("trade_date"), func.sum(ImportedTrade.realized_pnl).label("daily_pnl"),
    ).where(ImportedTrade.realized_pnl != 0).group_by(date_col).order_by(date_col)
    result = await db.execute(q)
    cumulative = 0.0; points = []
    for row in result.all():
        cumulative += float(row.daily_pnl)
        points.append(CumulativePnLPoint(date=str(row.trade_date), cumulative_pnl=round(cumulative, 2), daily_pnl=round(float(row.daily_pnl), 2)))
    return points
