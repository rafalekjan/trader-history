from datetime import datetime, date
from pydantic import BaseModel


class ImportResult(BaseModel):
    status: str
    imported: int
    message: str = ""


class ImportedTradeOut(BaseModel):
    id: int
    account_id: str
    asset_category: str
    currency: str
    symbol: str
    date_time: datetime
    quantity: float
    trade_price: float
    close_price: float | None = None
    proceeds: float
    commission: float
    realized_pnl: float
    mtm_pnl: float
    code: str

    model_config = {"from_attributes": True}


class DailyPnL(BaseModel):
    date: str
    pnl: float
    trade_count: int
    wins: int
    losses: int


class MonthlyStats(BaseModel):
    year: int
    month: int
    total_pnl: float
    trade_count: int
    wins: int
    losses: int
    win_rate: float
    profit_factor: float
    daily: list[DailyPnL]


class CumulativePnLPoint(BaseModel):
    date: str
    cumulative_pnl: float
    daily_pnl: float


class TradeSummary(BaseModel):
    net_realized_pnl: float
    open_trades: int
    logged_trades: int
    win_rate: float


class OpenPositionOut(BaseModel):
    symbol: str
    asset_category: str
    quantity: float
    avg_price: float
    market_value: float
    current_price: float | None = None
    unrealized_pnl: float | None = None


class DayTradeEntry(BaseModel):
    symbol: str
    asset_category: str
    quantity: float
    trade_price: float
    realized_pnl: float
    status: str


class DayDetail(BaseModel):
    date: str
    realized_pnl: float
    wins: int
    losses: int
    trims: int
    trades: list[DayTradeEntry]


class TradeRef(BaseModel):
    symbol: str
    pnl: float
    date: str


class FullStats(BaseModel):
    net_realized_pnl: float
    win_rate: float
    closed_trades: int
    profit_factor: float
    avg_win: float
    avg_loss: float
    best_trade: TradeRef | None
    worst_trade: TradeRef | None


class DepositOut(BaseModel):
    currency: str
    settle_date: date
    description: str
    amount: float

    model_config = {"from_attributes": True}


class DepositsResponse(BaseModel):
    deposits: list[DepositOut]
    total_native: dict[str, float]
    total_usd: float
