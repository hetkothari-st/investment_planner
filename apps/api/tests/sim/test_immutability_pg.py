"""The recommendations table rejects UPDATE on everything except status.
Postgres-only: the trigger lives in migration 0003."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

PG_URL = os.environ.get("CORPUS_TEST_PG_URL")
API_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(not PG_URL, reason="CORPUS_TEST_PG_URL not set")


async def test_trigger_rejects_everything_but_status():
    env = os.environ | {"DATABASE_URL": PG_URL}
    run = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_ROOT, env=env, capture_output=True, text=True,
    )
    assert run.returncode == 0, run.stderr

    engine = create_async_engine(PG_URL)
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM falsifiers"))
        await conn.execute(text("DELETE FROM calibration_results"))
        await conn.execute(text("DELETE FROM sim_marks"))
        await conn.execute(text("DELETE FROM sim_positions"))
        await conn.execute(text("DELETE FROM recommendations"))
        await conn.execute(
            text(
                """
                INSERT INTO recommendations
                  (id, isin, horizon, expires_on, ref_price, band_bear_pct,
                   band_base_pct, band_bull_pct, conviction, suggested_size_inr,
                   score_snapshot, weights_version, report_md,
                   net_of_costs_hurdle_pct)
                VALUES
                  ('00000000-0000-0000-0000-000000000001', 'INE000TEST01', 'MID',
                   '2027-01-01', 500, -15, 8, 25, 'MODERATE', 50000,
                   '{}'::jsonb, 'manual', 'frozen thesis', 0)
                """
            )
        )

    async with engine.begin() as conn:
        with pytest.raises(DBAPIError, match="immutable"):
            await conn.execute(
                text(
                    "UPDATE recommendations SET report_md = 'rewritten history' "
                    "WHERE id = '00000000-0000-0000-0000-000000000001'"
                )
            )

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE recommendations SET status = 'INVALIDATED' "
                "WHERE id = '00000000-0000-0000-0000-000000000001'"
            )
        )
        kept = await conn.execute(
            text(
                "SELECT report_md, status FROM recommendations "
                "WHERE id = '00000000-0000-0000-0000-000000000001'"
            )
        )
        row = kept.one()
        assert row.report_md == "frozen thesis"
        assert row.status == "INVALIDATED"
    await engine.dispose()
