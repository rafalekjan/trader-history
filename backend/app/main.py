import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from app.routers import csv_import, analytics, trade_ops
from app.database import async_session
from app.models import ImportedTrade
from app.services.price_service import refresh_prices

PRICE_INTERVAL = 300


async def _refresh_loop():
    await asyncio.sleep(5)
    while True:
        try:
            async with async_session() as db:
                q = select(
                    ImportedTrade.symbol, ImportedTrade.asset_category,
                ).group_by(
                    ImportedTrade.symbol, ImportedTrade.asset_category,
                ).having(func.sum(ImportedTrade.quantity) != 0)
                result = await db.execute(q)
                symbols = [(r.symbol, r.asset_category) for r in result.all()]

            if symbols:
                updated = await asyncio.to_thread(refresh_prices, symbols)
                print(f"[prices] refreshed {len(updated)}/{len(symbols)} symbols")
        except Exception as e:
            print(f"[prices] error: {e}")

        await asyncio.sleep(PRICE_INTERVAL)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(_refresh_loop())
    yield
    task.cancel()


app = FastAPI(title="Trader History", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(csv_import.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(trade_ops.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
