from datetime import date

from sqlalchemy import select

from corpus.db.models import UniverseMembership
from corpus.ingest.jobs.universe import (
    Constituent,
    membership_diff,
    parse_constituents_csv,
    sync_universe,
)

CSV = """\
Company Name,Industry,Symbol,Series,ISIN Code
Reliance Industries Ltd.,Oil Gas & Consumable Fuels,RELIANCE,EQ,INE002A01018
Infosys Ltd.,Information Technology,INFY,EQ,INE009A01021
Rows Without ISIN Are Skipped,Misc,JUNK,EQ,
"""


def test_parse_constituents_csv():
    parsed = parse_constituents_csv(CSV)
    assert len(parsed) == 2
    assert parsed[0] == Constituent(
        isin="INE002A01018",
        name="Reliance Industries Ltd.",
        industry="Oil Gas & Consumable Fuels",
        symbol="RELIANCE",
    )


def test_membership_diff():
    to_add, to_close = membership_diff({"A", "B"}, {"B", "C"})
    assert to_add == {"C"}
    assert to_close == {"A"}


async def test_sync_universe_dates_membership(session):
    day1, day2 = date(2026, 7, 1), date(2026, 7, 30)
    reliance = Constituent("INE002A01018", "Reliance Industries Ltd.", "Oil", "RELIANCE")
    infy = Constituent("INE009A01021", "Infosys Ltd.", "IT", "INFY")

    await sync_universe(session, [reliance, infy], day1)
    # Infosys drops out at the next sync.
    await sync_universe(session, [reliance], day2)

    rows = {
        m.isin: m
        for m in (await session.execute(select(UniverseMembership))).scalars()
    }
    assert rows["INE002A01018"].to_date is None  # still a member
    assert rows["INE009A01021"].from_date == day1
    assert rows["INE009A01021"].to_date == day2  # history preserved, not deleted
