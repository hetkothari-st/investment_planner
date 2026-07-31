"""Corporate actions ingestion.

Kite does not serve corporate actions reliably (docs/02), so records arrive
from a Source-protocol implementation or a hand-maintained CSV. The CSV path
is deliberate: a wrong split ratio silently corrupts every adjusted close, so
until a trustworthy automated source is wired, actions enter through a file
the owner can audit line by line.

CSV columns: isin,ex_date,action_type,ratio_from,ratio_to,amount,source
"""

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from corpus.db.models import CorporateAction
from corpus.db.upsert import upsert_rows
from corpus.ingest.runs import ingest_run

VALID_TYPES = {"SPLIT", "BONUS", "DIVIDEND", "RIGHTS", "MERGER"}


def parse_actions_csv(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open() as f:
        for i, line in enumerate(csv.DictReader(f), start=2):
            action_type = line["action_type"].strip().upper()
            if action_type not in VALID_TYPES:
                raise ValueError(f"{path}:{i}: unknown action_type {action_type!r}")
            ratio_from = line.get("ratio_from", "").strip()
            ratio_to = line.get("ratio_to", "").strip()
            if action_type in ("SPLIT", "BONUS") and not (ratio_from and ratio_to):
                raise ValueError(f"{path}:{i}: {action_type} requires ratio_from/ratio_to")
            amount = line.get("amount", "").strip()
            rows.append(
                {
                    "isin": line["isin"].strip(),
                    "ex_date": date.fromisoformat(line["ex_date"].strip()),
                    "action_type": action_type,
                    "ratio_from": Decimal(ratio_from) if ratio_from else None,
                    "ratio_to": Decimal(ratio_to) if ratio_to else None,
                    "amount": Decimal(amount) if amount else None,
                    "source": line.get("source", "").strip() or "manual_csv",
                }
            )
    return rows


async def ingest_corporate_actions(
    session: AsyncSession, rows: list[dict[str, Any]], as_of: date, source: str
) -> int:
    async with ingest_run(session, "ingest_corporate_actions", source, as_of) as rec:
        written = await upsert_rows(
            session,
            CorporateAction.__table__,
            rows,
            key_cols=["isin", "ex_date", "action_type"],
        )
        rec.add_rows(written)
    return rec.rows_written
