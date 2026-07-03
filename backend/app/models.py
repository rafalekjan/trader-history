from datetime import datetime, date
from sqlalchemy import String, Integer, Float, DateTime, Date, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ImportedTrade(Base):
    __tablename__ = "imported_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[str] = mapped_column(String(50), nullable=False)
    asset_category: Mapped[str] = mapped_column(String(50), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    symbol: Mapped[str] = mapped_column(String(100), nullable=False)
    date_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    trade_price: Mapped[float] = mapped_column(Float, nullable=False)
    close_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    proceeds: Mapped[float] = mapped_column(Float, default=0)
    commission: Mapped[float] = mapped_column(Float, default=0)
    basis: Mapped[float | None] = mapped_column(Float, nullable=True)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0)
    mtm_pnl: Mapped[float] = mapped_column(Float, default=0)
    code: Mapped[str] = mapped_column(String(50), default="")

    __table_args__ = (
        UniqueConstraint(
            "asset_category", "symbol", "date_time", "quantity", "trade_price", "proceeds",
            name="uq_imported_trade",
        ),
    )


class ImportedDeposit(Base):
    __tablename__ = "imported_deposits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[str] = mapped_column(String(50), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    settle_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("account_id", "currency", "settle_date", "description", "amount", name="uq_deposit"),
    )
