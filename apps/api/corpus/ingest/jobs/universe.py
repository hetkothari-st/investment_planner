"""Universe membership — Nifty 500 constituents, stored as a dated table.

Membership history is preserved (survivorship bias matters for backtests):
a sync closes out departed members by setting to_date and opens new members
at from_date = as_of. The constituent list comes from NSE's published CSV.
"""

import csv
import io
from dataclasses import dataclass
from datetime import date

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from corpus.db.models import Company, UniverseMembership
from corpus.db.upsert import upsert_rows
from corpus.ingest.runs import ingest_run

NIFTY500_CSV_URL = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
INDEX_NAME = "NIFTY500"


@dataclass(frozen=True)
class Constituent:
    isin: str
    name: str
    industry: str | None
    symbol: str


def parse_constituents_csv(text: str) -> list[Constituent]:
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        isin = (row.get("ISIN Code") or "").strip()
        if not isin:
            continue
        out.append(
            Constituent(
                isin=isin,
                name=(row.get("Company Name") or "").strip(),
                industry=(row.get("Industry") or "").strip() or None,
                symbol=(row.get("Symbol") or "").strip(),
            )
        )
    return out


def membership_diff(
    current_isins: set[str], fetched_isins: set[str]
) -> tuple[set[str], set[str]]:
    """Returns (to_add, to_close)."""
    return fetched_isins - current_isins, current_isins - fetched_isins


async def fetch_constituents(url: str = NIFTY500_CSV_URL) -> list[Constituent]:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "corpus-ingest/0.1"})
        resp.raise_for_status()
    return parse_constituents_csv(resp.text)


async def sync_universe(
    session: AsyncSession, constituents: list[Constituent], as_of: date
) -> None:
    async with ingest_run(session, "sync_universe", "nse_indices", as_of) as rec:
        company_rows = [
            {"isin": c.isin, "name": c.name, "industry": c.industry}
            for c in constituents
        ]
        rec.add_rows(
            await upsert_rows(
                session, Company.__table__, company_rows, key_cols=["isin"]
            )
        )

        open_members = {
            m.isin: m
            for m in (
                await session.execute(
                    select(UniverseMembership).where(
                        UniverseMembership.index_name == INDEX_NAME,
                        UniverseMembership.to_date.is_(None),
                    )
                )
            ).scalars()
        }
        to_add, to_close = membership_diff(
            set(open_members), {c.isin for c in constituents}
        )
        for isin in to_close:
            open_members[isin].to_date = as_of
        for isin in to_add:
            session.add(
                UniverseMembership(isin=isin, index_name=INDEX_NAME, from_date=as_of)
            )
        rec.add_rows(len(to_add) + len(to_close))


async def current_universe_isins(session: AsyncSession) -> list[str]:
    """Nifty 500 members plus anything the user pinned."""
    return list(
        (
            await session.execute(
                select(UniverseMembership.isin)
                .where(UniverseMembership.to_date.is_(None))
                .distinct()
            )
        )
        .scalars()
        .all()
    )
