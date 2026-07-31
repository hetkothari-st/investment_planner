"""Instrument master refresh — full Kite dump, upserted idempotently."""

from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from corpus.db.models import Instrument
from corpus.db.upsert import upsert_rows
from corpus.ingest.kite.client import KiteClient
from corpus.ingest.runs import ingest_run


def _to_row(item: dict[str, Any]) -> dict[str, Any]:
    expiry = item.get("expiry") or None
    if expiry == "":
        expiry = None
    return {
        "instrument_token": item["instrument_token"],
        "tradingsymbol": item["tradingsymbol"],
        "exchange": item["exchange"],
        "name": item.get("name") or None,
        "isin": item.get("isin") or None,
        "segment": item.get("segment") or None,
        "lot_size": item.get("lot_size"),
        "tick_size": item.get("tick_size"),
        "expiry": expiry,
        "instrument_type": item.get("instrument_type") or None,
    }


async def refresh_instruments(
    session: AsyncSession, client: KiteClient, as_of: date, exchange: str = "NSE"
) -> int:
    async with ingest_run(session, "refresh_instruments", "kite", as_of) as rec:
        dump = await client.instruments(exchange)
        rows = [_to_row(item) for item in dump]
        written = await upsert_rows(
            session, Instrument.__table__, rows, key_cols=["instrument_token"]
        )
        rec.add_rows(written)
    return rec.rows_written
