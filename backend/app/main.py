import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import analytics, csv_import, positions, trades
from app.routers.positions import fetch_open_symbols
from app.services.price_service import refresh_prices

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("app")

PRICE_REFRESH_SECONDS = 300


async def _price_refresh_loop():
    await asyncio.sleep(5)  # let the app finish startup / migrations settle
    while True:
        try:
            symbols = await fetch_open_symbols()
            if symbols:
                updated = await refresh_prices(symbols)
                logger.info("prices refreshed: %d/%d symbols", len(updated), len(symbols))
        except Exception:
            logger.exception("price refresh failed")
        await asyncio.sleep(PRICE_REFRESH_SECONDS)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(_price_refresh_loop())
    yield
    task.cancel()


app = FastAPI(title="Trader History", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analytics.router, prefix="/api")
app.include_router(csv_import.router, prefix="/api")
app.include_router(positions.router, prefix="/api")
app.include_router(trades.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
