from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import get_db
from app.models import ImportedTrade, ImportedDeposit
from app.schemas import ImportResult
from app.services.csv_parser import parse_ibkr_csv

router = APIRouter(tags=["csv-import"])


async def _insert_new_rows(db: AsyncSession, model, rows: list[dict], constraint: str, account_id: str) -> int:
    """Insert rows one by one, silently skipping duplicates; returns rows actually inserted."""
    inserted = 0
    for values in rows:
        stmt = pg_insert(model).values(
            account_id=account_id, **values,
        ).on_conflict_do_nothing(constraint=constraint)
        if (await db.execute(stmt)).rowcount > 0:
            inserted += 1
    return inserted


@router.post("/csv/upload", response_model=ImportResult)
async def upload_csv(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    content = await file.read()
    parsed = parse_ibkr_csv(content.decode("utf-8-sig"))

    trade_count = await _insert_new_rows(db, ImportedTrade, parsed.trades, "uq_imported_trade", parsed.account_id)
    dep_count = await _insert_new_rows(db, ImportedDeposit, parsed.deposits, "uq_deposit", parsed.account_id)
    await db.commit()

    return ImportResult(
        status="ok",
        imported=trade_count,
        message=f"Imported {trade_count} trades, {dep_count} deposits ({len(parsed.trades)} trades in file)",
    )
