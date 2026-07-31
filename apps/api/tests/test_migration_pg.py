"""Runs the real Alembic migration against Postgres when one is available.

Set CORPUS_TEST_PG_URL (postgresql+asyncpg://...) to enable; skipped otherwise.
CI provides a TimescaleDB service so the hypertable path is exercised there.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

PG_URL = os.environ.get("CORPUS_TEST_PG_URL")
API_ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(not PG_URL, reason="CORPUS_TEST_PG_URL not set")

EXPECTED_TABLES = {
    "instruments",
    "companies",
    "universe_membership",
    "trading_calendar",
    "ohlcv_daily",
    "corporate_actions",
    "ingest_run",
}


async def test_upgrade_head_creates_data_spine():
    # Start from a clean schema — other tests share this database.
    engine = create_async_engine(PG_URL, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        from sqlalchemy import text

        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()

    env = os.environ | {"DATABASE_URL": PG_URL}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    engine = create_async_engine(PG_URL)
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
    await engine.dispose()
    assert EXPECTED_TABLES <= tables
