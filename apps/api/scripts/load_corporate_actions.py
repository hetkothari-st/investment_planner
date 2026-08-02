"""Load corporate actions from a hand-maintained CSV, then re-adjust closes.

    uv run python scripts/load_corporate_actions.py data/corporate_actions.csv

CSV columns: isin,ex_date,action_type,ratio_from,ratio_to,amount,source
See corpus/ingest/jobs/corporate_actions.py for why this is a file and not
an automated fetch.
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from corpus.db.models import Instrument
from corpus.db.session import get_sessionmaker
from corpus.ingest.jobs.corporate_actions import (
    ingest_corporate_actions,
    parse_actions_csv,
)
from corpus.ingest.jobs.ohlcv import recompute_adjusted_closes


async def run(path: Path) -> int:
    rows = parse_actions_csv(path)
    today = datetime.now(UTC).date()
    sessionmaker = get_sessionmaker()

    async with sessionmaker() as session:
        written = await ingest_corporate_actions(session, rows, today, source="manual_csv")
    print(f"corporate_actions: {written} rows written from {len(rows)} in file")

    touched_isins = {r["isin"] for r in rows}
    async with sessionmaker() as session:
        tokens = (
            (
                await session.execute(
                    select(Instrument.instrument_token).where(
                        Instrument.isin.in_(touched_isins)
                    )
                )
            )
            .scalars()
            .all()
        )
        for token in tokens:
            changed = await recompute_adjusted_closes(session, token)
            if changed:
                print(f"  adjusted {changed} closes for token {token}")
        await session.commit()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    args = parser.parse_args()
    return asyncio.run(run(args.csv))


if __name__ == "__main__":
    sys.exit(main())
