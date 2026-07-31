"""Resumable historical backfill — docs/02-DATA-LAYER.md.

    uv run python scripts/backfill.py --since 2016-07-30
    uv run python scripts/backfill.py --symbols RELIANCE INFY --since 2016-07-30
    uv run python scripts/backfill.py --only universe
    uv run python scripts/backfill.py --only ohlcv --resume

Stages: instruments -> universe -> ohlcv -> calendar -> adjust.
State is checkpointed to var/backfill.state.json after every symbol, so a crash
resumes where it stopped instead of restarting a 6-minute (or 6-hour) run.
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from redis.asyncio import Redis
from sqlalchemy import select

from corpus.config import get_settings
from corpus.db.models import Instrument, UniverseMembership
from corpus.db.session import get_sessionmaker
from corpus.ingest.jobs.calendar import (
    NIFTY50_INSTRUMENT_TOKEN,
    build_calendar_from_index,
)
from corpus.ingest.jobs.instruments import refresh_instruments
from corpus.ingest.jobs.ohlcv import (
    recompute_adjusted_closes,
)
from corpus.ingest.jobs.universe import fetch_constituents, sync_universe
from corpus.ingest.kite.client import KiteClient
from corpus.ingest.runs import ingest_run

STATE_FILE = Path("var/backfill.state.json")
STAGES = ("instruments", "universe", "ohlcv", "calendar", "adjust")


def load_state(resume: bool) -> dict:
    if resume and STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"done_stages": [], "ohlcv_done_tokens": [], "adjust_done_tokens": []}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


async def resolve_tokens(session, symbols: list[str] | None) -> list[int]:
    """Universe ISINs -> NSE equity instrument tokens (plus the index)."""
    q = select(Instrument.instrument_token, Instrument.tradingsymbol).where(
        Instrument.exchange == "NSE"
    )
    if symbols:
        q = q.where(Instrument.tradingsymbol.in_(symbols))
    else:
        universe = select(UniverseMembership.isin).where(
            UniverseMembership.to_date.is_(None)
        )
        q = q.where(Instrument.isin.in_(universe))
    tokens = [row.instrument_token for row in (await session.execute(q)).all()]
    if not symbols and NIFTY50_INSTRUMENT_TOKEN not in tokens:
        tokens.insert(0, NIFTY50_INSTRUMENT_TOKEN)  # index first: calendar needs it
    return tokens


async def run(args: argparse.Namespace) -> int:
    state = load_state(args.resume)
    today = datetime.now(UTC).date()
    since: date = args.since
    only = set(args.only) if args.only else set(STAGES)

    redis = Redis.from_url(get_settings().redis_url)
    client = KiteClient(redis)
    sessionmaker = get_sessionmaker()

    try:
        if "instruments" in only and "instruments" not in state["done_stages"]:
            async with sessionmaker() as session:
                n = await refresh_instruments(session, client, today)
            print(f"instruments: {n} rows")
            state["done_stages"].append("instruments")
            save_state(state)

        if "universe" in only and "universe" not in state["done_stages"]:
            constituents = await fetch_constituents()
            async with sessionmaker() as session:
                await sync_universe(session, constituents, today)
            print(f"universe: {len(constituents)} constituents")
            state["done_stages"].append("universe")
            save_state(state)

        if "ohlcv" in only:
            async with sessionmaker() as session:
                tokens = await resolve_tokens(session, args.symbols)
            done = set(state["ohlcv_done_tokens"])
            todo = [t for t in tokens if t not in done]
            print(f"ohlcv: {len(todo)} of {len(tokens)} symbols remaining")
            for i, token in enumerate(todo, 1):
                async with sessionmaker() as session:
                    async with ingest_run(
                        session, "backfill_ohlcv", "kite", today
                    ) as rec:
                        from corpus.ingest.jobs.ohlcv import ingest_symbol

                        try:
                            await ingest_symbol(
                                session, client, rec, token, since, today
                            )
                        except Exception as exc:
                            rec.record_error(str(token), repr(exc))
                            print(f"  [{i}/{len(todo)}] {token} FAILED: {exc!r}")
                        else:
                            print(f"  [{i}/{len(todo)}] {token}: {rec.rows_written} rows")
                state["ohlcv_done_tokens"].append(token)
                save_state(state)

        if "calendar" in only and "calendar" not in state["done_stages"]:
            async with sessionmaker() as session:
                n = await build_calendar_from_index(session, since, today)
                await session.commit()
            print(f"calendar: {n} rows")
            state["done_stages"].append("calendar")
            save_state(state)

        if "adjust" in only:
            async with sessionmaker() as session:
                tokens = await resolve_tokens(session, args.symbols)
            done = set(state["adjust_done_tokens"])
            todo = [t for t in tokens if t not in done]
            print(f"adjust: {len(todo)} of {len(tokens)} symbols remaining")
            for token in todo:
                async with sessionmaker() as session:
                    n = await recompute_adjusted_closes(session, token)
                    await session.commit()
                state["adjust_done_tokens"].append(token)
                save_state(state)
            print("adjust: done")
    finally:
        await redis.aclose()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="*", help="tradingsymbols; default = universe")
    parser.add_argument(
        "--since",
        type=date.fromisoformat,
        default=date(datetime.now(UTC).year - 10, 1, 1),
        help="backfill start date (default: 10 years back)",
    )
    parser.add_argument("--only", nargs="*", choices=STAGES, help="run only these stages")
    parser.add_argument(
        "--resume", action="store_true", help="continue from var/backfill.state.json"
    )
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
