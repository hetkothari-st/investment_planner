"""Daily OHLCV ingestion + corporate-action-adjusted close recomputation."""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from corpus.db.models import CorporateAction, Instrument, OhlcvDaily
from corpus.db.upsert import upsert_rows
from corpus.ingest.adjust import ActionRatio, Bar, adjusted_closes
from corpus.ingest.kite.client import KiteClient
from corpus.ingest.runs import RunRecorder, ingest_run


def _candle_to_row(instrument_token: int, candle: dict[str, Any]) -> dict[str, Any]:
    ts = candle["date"]
    trade_date = ts.date() if hasattr(ts, "date") else ts
    return {
        "instrument_token": instrument_token,
        "trade_date": trade_date,
        "open": Decimal(str(candle["open"])),
        "high": Decimal(str(candle["high"])),
        "low": Decimal(str(candle["low"])),
        "close": Decimal(str(candle["close"])),
        "volume": candle.get("volume"),
        "adj_close": None,  # filled by recompute_adjusted_closes
        "source": "kite",
    }


async def ingest_symbol(
    session: AsyncSession,
    client: KiteClient,
    rec: RunRecorder,
    instrument_token: int,
    since: date,
    until: date,
) -> None:
    candles = await client.historical_daily(instrument_token, since, until)
    rows = [_candle_to_row(instrument_token, c) for c in candles]
    written = await upsert_rows(
        session,
        OhlcvDaily.__table__,
        rows,
        key_cols=["instrument_token", "trade_date"],
        skip_update_cols=("ingested_at", "adj_close"),
    )
    rec.add_rows(written)


async def ingest_ohlcv_daily(
    session: AsyncSession,
    client: KiteClient,
    tokens: list[int],
    since: date,
    until: date,
    as_of: date,
) -> RunRecorder:
    """Partial-tolerant: one bad symbol records an error, the batch continues."""
    async with ingest_run(session, "ingest_ohlcv_daily", "kite", as_of) as rec:
        for token in tokens:
            try:
                await ingest_symbol(session, client, rec, token, since, until)
            except Exception as exc:
                rec.record_error(str(token), repr(exc))
        return rec


async def recompute_adjusted_closes(
    session: AsyncSession, instrument_token: int
) -> int:
    """Back-adjust closes for one instrument from its corporate actions.

    Idempotent: writes only rows whose adj_close actually changes.
    """
    isin = await session.scalar(
        select(Instrument.isin).where(Instrument.instrument_token == instrument_token)
    )
    bars = (
        await session.execute(
            select(OhlcvDaily.trade_date, OhlcvDaily.close, OhlcvDaily.adj_close)
            .where(OhlcvDaily.instrument_token == instrument_token)
            .order_by(OhlcvDaily.trade_date)
        )
    ).all()
    if not bars:
        return 0

    actions: list[ActionRatio] = []
    if isin:
        ca_rows = (
            await session.execute(
                select(CorporateAction).where(
                    CorporateAction.isin == isin,
                    CorporateAction.action_type.in_(("SPLIT", "BONUS")),
                )
            )
        ).scalars()
        actions = [
            ActionRatio(a.ex_date, a.action_type, a.ratio_from, a.ratio_to)
            for a in ca_rows
        ]

    adj = adjusted_closes(
        [Bar(b.trade_date, b.close) for b in bars if b.close is not None], actions
    )
    changed = [
        {
            "instrument_token": instrument_token,
            "trade_date": b.trade_date,
            "adj_close": adj[b.trade_date],
        }
        for b in bars
        if b.close is not None and b.adj_close != adj[b.trade_date]
    ]
    for row in changed:
        await session.execute(
            OhlcvDaily.__table__.update()
            .where(
                OhlcvDaily.instrument_token == row["instrument_token"],
                OhlcvDaily.trade_date == row["trade_date"],
            )
            .values(adj_close=row["adj_close"])
        )
    return len(changed)
