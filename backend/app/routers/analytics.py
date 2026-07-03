from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc, asc, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session
from app.models import ImportedTrade, ImportedDeposit
from app.schemas import (
    ImportedTradeOut, MonthlyStats, DailyPnL, CumulativePnLPoint,
    TradeSummary, DayDetail, DayTradeEntry, OpenPositionOut,
    FullStats, TradeRef, DepositsResponse, DepositOut,
)
from app.services import price_service
from app.constants import OPTION_CATEGORY, contract_multiplier

router = APIRouter(tags=["analytics"])

ASSET_MAP = {"Stock": "Stocks", "Option": OPTION_CATEGORY, "Future": "Futures"}

# IBKR "code" column holds ";"-separated flags; "C" marks a closing trade.
IS_CLOSING = ImportedTrade.code.regexp_match(r"(^|;)C(;|$)")
HAS_PNL = ImportedTrade.realized_pnl != 0

_trade_date = func.date(ImportedTrade.date_time)


def _profit_factor(gross_profit: float, gross_loss: float) -> float:
    return round(gross_profit / gross_loss, 2) if gross_loss > 0 else round(gross_profit, 2)


async def fetch_open_symbols() -> list[tuple[str, str]]:
    """(symbol, asset_category) pairs for every position with a non-zero net quantity."""
    async with async_session() as db:
        result = await db.execute(
            select(ImportedTrade.symbol, ImportedTrade.asset_category)
            .group_by(ImportedTrade.symbol, ImportedTrade.asset_category)
            .having(func.sum(ImportedTrade.quantity) != 0)
        )
        return [(r.symbol, r.asset_category) for r in result.all()]


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


@router.get("/analytics/summary", response_model=TradeSummary)
async def get_summary(db: AsyncSession = Depends(get_db)):
    stats = (await db.execute(
        select(
            func.coalesce(func.sum(ImportedTrade.realized_pnl), 0).label("net_pnl"),
            func.count().filter(IS_CLOSING).label("logged"),
            func.count().filter(IS_CLOSING, ImportedTrade.realized_pnl > 0).label("wins"),
        )
    )).one()

    open_count = (await db.execute(
        select(func.count()).select_from(
            select(ImportedTrade.symbol)
            .group_by(ImportedTrade.symbol)
            .having(func.sum(ImportedTrade.quantity) != 0)
            .subquery()
        )
    )).scalar_one()

    return TradeSummary(
        net_realized_pnl=round(float(stats.net_pnl), 2),
        open_trades=int(open_count),
        logged_trades=stats.logged,
        win_rate=round(stats.wins / stats.logged * 100, 1) if stats.logged else 0,
    )


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


@router.get("/analytics/day-detail", response_model=DayDetail)
async def get_day_detail(
    date_str: str = Query(..., alias="date", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(ImportedTrade)
        .where(cast(ImportedTrade.date_time, Date) == date.fromisoformat(date_str), HAS_PNL)
        .order_by(desc(ImportedTrade.realized_pnl))
    )).scalars().all()

    counts = {"WIN": 0, "LOSS": 0, "TRIM": 0}
    entries: list[DayTradeEntry] = []
    for t in rows:
        codes = t.code.split(";")
        # A partial close ("C" + "P") is a trim rather than a full win/loss exit.
        status = "TRIM" if ("C" in codes and "P" in codes) else ("WIN" if t.realized_pnl > 0 else "LOSS")
        counts[status] += 1
        entries.append(DayTradeEntry(
            symbol=t.symbol,
            asset_category=t.asset_category,
            quantity=t.quantity,
            trade_price=t.trade_price,
            realized_pnl=round(t.realized_pnl, 2),
            status=status,
        ))

    return DayDetail(
        date=date_str,
        realized_pnl=round(sum(t.realized_pnl for t in rows), 2),
        wins=counts["WIN"], losses=counts["LOSS"], trims=counts["TRIM"],
        trades=entries,
    )


@router.get("/analytics/stats", response_model=FullStats)
async def get_full_stats(
    start_date: str | None = None,
    end_date: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(ImportedTrade).where(IS_CLOSING, HAS_PNL)
    if start_date:
        q = q.where(cast(ImportedTrade.date_time, Date) >= date.fromisoformat(start_date))
    if end_date:
        q = q.where(cast(ImportedTrade.date_time, Date) <= date.fromisoformat(end_date))

    trades = (await db.execute(q)).scalars().all()
    if not trades:
        return FullStats(
            net_realized_pnl=0, win_rate=0, closed_trades=0, profit_factor=0,
            avg_win=0, avg_loss=0, best_trade=None, worst_trade=None,
        )

    wins = [t.realized_pnl for t in trades if t.realized_pnl > 0]
    losses = [t.realized_pnl for t in trades if t.realized_pnl < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    best = max(trades, key=lambda t: t.realized_pnl)
    worst = min(trades, key=lambda t: t.realized_pnl)

    def trade_ref(t: ImportedTrade) -> TradeRef:
        return TradeRef(symbol=t.symbol, pnl=round(t.realized_pnl, 2), date=str(t.date_time.date()))

    return FullStats(
        net_realized_pnl=round(sum(t.realized_pnl for t in trades), 2),
        win_rate=round(len(wins) / len(trades) * 100, 1),
        closed_trades=len(trades),
        profit_factor=_profit_factor(gross_profit, gross_loss),
        avg_win=round(gross_profit / len(wins), 2) if wins else 0,
        avg_loss=round(-gross_loss / len(losses), 2) if losses else 0,
        best_trade=trade_ref(best),
        worst_trade=trade_ref(worst),
    )


@router.get("/analytics/deposits", response_model=DepositsResponse)
async def get_deposits(db: AsyncSession = Depends(get_db)):
    deps = (await db.execute(
        select(ImportedDeposit).order_by(ImportedDeposit.settle_date)
    )).scalars().all()

    totals: dict[str, float] = defaultdict(float)
    for d in deps:
        totals[d.currency] += d.amount

    total_usd = sum(
        amount * price_service.get_fx_usd_rate(currency)
        for currency, amount in totals.items()
    )

    return DepositsResponse(
        deposits=[DepositOut.model_validate(d) for d in deps],
        total_native=dict(totals),
        total_usd=round(total_usd, 2),
    )


@router.get("/analytics/monthly-pnl", response_model=MonthlyStats)
async def get_monthly_pnl(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(_trade_date.label("trade_date"), ImportedTrade.realized_pnl)
        .where(
            func.extract("year", ImportedTrade.date_time) == year,
            func.extract("month", ImportedTrade.date_time) == month,
            HAS_PNL,
        )
        .order_by(_trade_date)
    )).all()

    by_day: dict[str, dict] = defaultdict(lambda: {"pnl": 0.0, "trades": 0, "wins": 0, "losses": 0})
    for row in rows:
        day = by_day[str(row.trade_date)]
        day["pnl"] += row.realized_pnl
        day["trades"] += 1
        day["wins" if row.realized_pnl > 0 else "losses"] += 1

    daily = [
        DailyPnL(date=d, pnl=round(v["pnl"], 2), trade_count=v["trades"], wins=v["wins"], losses=v["losses"])
        for d, v in sorted(by_day.items())
    ]

    total_trades = sum(d.trade_count for d in daily)
    total_wins = sum(d.wins for d in daily)
    gross_profit = sum(d.pnl for d in daily if d.pnl > 0)
    gross_loss = abs(sum(d.pnl for d in daily if d.pnl < 0))

    return MonthlyStats(
        year=year, month=month,
        total_pnl=round(sum(d.pnl for d in daily), 2),
        trade_count=total_trades,
        wins=total_wins,
        losses=sum(d.losses for d in daily),
        win_rate=round(total_wins / total_trades * 100, 1) if total_trades else 0,
        profit_factor=_profit_factor(gross_profit, gross_loss),
        daily=daily,
    )


@router.get("/analytics/cumulative-pnl", response_model=list[CumulativePnLPoint])
async def get_cumulative_pnl(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(_trade_date.label("trade_date"), func.sum(ImportedTrade.realized_pnl).label("daily_pnl"))
        .where(HAS_PNL)
        .group_by(_trade_date)
        .order_by(_trade_date)
    )).all()

    points: list[CumulativePnLPoint] = []
    cumulative = 0.0
    for row in rows:
        daily = float(row.daily_pnl)
        cumulative += daily
        points.append(CumulativePnLPoint(
            date=str(row.trade_date),
            cumulative_pnl=round(cumulative, 2),
            daily_pnl=round(daily, 2),
        ))
    return points
