import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import AppSetting
from app.config import settings as app_settings

IBKR_BASE_URL = "https://api.ibkr.com/v1/api"


class IBKRClient:
    def __init__(self, api_key: str, account_id: str):
        self.api_key = api_key
        self.account_id = account_id
        self._client = httpx.AsyncClient(
            base_url=IBKR_BASE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    async def close(self):
        await self._client.aclose()

    async def get_trades(self) -> list[dict]:
        resp = await self._client.get(f"/portfolio/{self.account_id}/trades")
        resp.raise_for_status()
        return resp.json()

    async def get_positions(self) -> list[dict]:
        resp = await self._client.get(f"/portfolio/{self.account_id}/positions/0")
        resp.raise_for_status()
        return resp.json()

    async def get_account_summary(self) -> dict:
        resp = await self._client.get(f"/portfolio/{self.account_id}/summary")
        resp.raise_for_status()
        return resp.json()

    async def get_price_history(self, conid: int, period: str = "1y", bar: str = "1d") -> list[dict]:
        resp = await self._client.get(
            "/iserver/marketdata/history",
            params={"conid": conid, "period": period, "bar": bar},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])


async def get_ibkr_client(db: AsyncSession) -> IBKRClient:
    fernet = app_settings.get_fernet()

    result = await db.execute(select(AppSetting).where(AppSetting.key == "ibkr_api_key"))
    api_key_row = result.scalar_one_or_none()
    if not api_key_row:
        raise ValueError("IBKR API key not configured. Go to Settings to add it.")
    api_key = fernet.decrypt(api_key_row.value.encode()).decode()

    result = await db.execute(select(AppSetting).where(AppSetting.key == "ibkr_account_id"))
    account_row = result.scalar_one_or_none()
    if not account_row:
        raise ValueError("IBKR Account ID not configured. Go to Settings to add it.")
    account_id = account_row.value

    return IBKRClient(api_key=api_key, account_id=account_id)
