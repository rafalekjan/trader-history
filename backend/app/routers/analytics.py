"""Aggregated P&L analytics: summaries, calendar data and deposits."""
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, asc, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ImportedTrade, ImportedDeposit
from app.schemas import (
    MonthlyStats, DailyPnL, CumulativePnLPoint, TradeSummary,
    DayDetail, DayTradeEntry, FullStats, TradeRef,
    DepositsResponse, DepositOut,
)
from app.services import price_service, trade_stats
from app.services.trade_stats import IS_CLOSING, HAS_PNL

router = APIRouter(tags=["analytics"])

_trade_date = func.date(ImportedTrade.date_time)


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
        win_rate=trade_stats.win_rate(stats.wins, stats.logged),
    )


@router.get("/analytics/day-detail", response_model=DayDetail)
async def get_day_detail(
    date_str: str = Query(..., alias="date", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(ImportedTrade)
        .where(cast(ImportedTrade.date_time, Date) == date.fromisoformat(date_str))
        .order_by(asc(ImportedTrade.date_time))
    )).scalars().all()

    counts = {"WIN": 0, "LOSS": 0, "TRIM": 0}
    entries: list[DayTradeEntry] = []
    for t in rows:
        status = trade_stats.trade_status(t)
        if status in counts:
            counts[status] += 1
        closed = status != "OPEN"
        entries.append(DayTradeEntry(
            symbol=t.symbol,
            asset_category=t.asset_category,
            quantity=t.quantity,
            side="BUY" if t.quantity > 0 else "SELL",
            trade_price=t.trade_price,
            entry_price=trade_stats.effective_entry_price(t) if closed else None,
            commission=round(t.commission, 2),
            net_amount=round(t.proceeds + t.commission, 2),
            realized_pnl=round(t.realized_pnl, 2) if closed else None,
            status=status,
        ))

    return DayDetail(
        date=date_str,
        realized_pnl=round(sum(t.realized_pnl for t in rows), 2),
        total_commission=round(sum(t.commission for t in rows), 2),
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

    pnls = [t.realized_pnl for t in trades]
    win_count = sum(1 for p in pnls if p > 0)
    loss_count = sum(1 for p in pnls if p < 0)
    gross_profit, gross_loss = trade_stats.gross_profit_loss(pnls)
    best = max(trades, key=lambda t: t.realized_pnl)
    worst = min(trades, key=lambda t: t.realized_pnl)

    def trade_ref(t: ImportedTrade) -> TradeRef:
        return TradeRef(symbol=t.symbol, pnl=round(t.realized_pnl, 2), date=str(t.date_time.date()))

    return FullStats(
        net_realized_pnl=round(sum(pnls), 2),
        win_rate=trade_stats.win_rate(win_count, len(trades)),
        closed_trades=len(trades),
        profit_factor=trade_stats.profit_factor(gross_profit, gross_loss),
        avg_win=round(gross_profit / win_count, 2) if win_count else 0,
        avg_loss=round(-gross_loss / loss_count, 2) if loss_count else 0,
        best_trade=trade_ref(best),
        worst_trade=trade_ref(worst),
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
    # Per-trade gross figures — daily aggregates would net wins against losses
    # within a day and skew the profit factor.
    gross_profit, gross_loss = trade_stats.gross_profit_loss(r.realized_pnl for r in rows)

    return MonthlyStats(
        year=year, month=month,
        total_pnl=round(sum(d.pnl for d in daily), 2),
        trade_count=total_trades,
        wins=total_wins,
        losses=sum(d.losses for d in daily),
        win_rate=trade_stats.win_rate(total_wins, total_trades),
        profit_factor=trade_stats.profit_factor(gross_profit, gross_loss),
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
