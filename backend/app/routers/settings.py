from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import AppSetting
from app.schemas import SettingIn, SettingOut
from app.config import settings as app_settings

router = APIRouter(tags=["settings"])


def _encrypt(value: str) -> str:
    return app_settings.get_fernet().encrypt(value.encode()).decode()


def _decrypt(value: str) -> str:
    return app_settings.get_fernet().decrypt(value.encode()).decode()


@router.get("/settings", response_model=list[SettingOut])
async def get_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppSetting))
    rows = result.scalars().all()
    out = []
    for row in rows:
        val = _decrypt(row.value) if row.is_encrypted else row.value
        masked = val[:4] + "****" if row.is_encrypted and len(val) > 4 else val
        out.append(SettingOut(
            key=row.key,
            value=masked,
            is_encrypted=row.is_encrypted,
            updated_at=row.updated_at,
        ))
    return out


@router.put("/settings")
async def upsert_setting(data: SettingIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppSetting).where(AppSetting.key == data.key))
    existing = result.scalar_one_or_none()

    stored_value = _encrypt(data.value) if data.is_secret else data.value

    if existing:
        existing.value = stored_value
        existing.is_encrypted = data.is_secret
    else:
        db.add(AppSetting(key=data.key, value=stored_value, is_encrypted=data.is_secret))

    await db.commit()
    return {"status": "ok", "key": data.key}


@router.delete("/settings/{key}")
async def delete_setting(key: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    existing = result.scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.commit()
    return {"status": "ok"}
