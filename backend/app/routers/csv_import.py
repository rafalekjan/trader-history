from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.database import get_db
from app.models import ImportedTrade, ImportedDeposit
from app.schemas import ImportResult
from app.services.csv_parser import parse_ibkr_csv

router = APIRouter(tags=["csv-import"])


@router.post("/csv/upload", response_model=ImportResult)
async def upload_csv(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    content = await file.read()
    text = content.decode("utf-8-sig")

    parsed = parse_ibkr_csv(text)
    account_id = parsed["account_id"]
    trades = parsed["trades"]
    deposits = parsed["deposits"]

    trade_count = 0
    for t in trades:
        stmt = pg_insert(ImportedTrade).values(
            account_id=account_id, **t,
        ).on_conflict_do_nothing(constraint="uq_imported_trade")
        result = await db.execute(stmt)
        if result.rowcount > 0:
            trade_count += 1

    dep_count = 0
    for d in deposits:
        stmt = pg_insert(ImportedDeposit).values(
            account_id=account_id, **d,
        ).on_conflict_do_nothing(constraint="uq_deposit")
        result = await db.execute(stmt)
        if result.rowcount > 0:
            dep_count += 1

    await db.commit()
    return ImportResult(
        status="ok",
        imported=trade_count,
        message=f"Imported {trade_count} trades, {dep_count} deposits ({len(trades)} trades in file)",
    )
