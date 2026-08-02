import json
from datetime import date

import pytest
from sqlalchemy import select

from corpus.db.models import IngestRun
from corpus.ingest.runs import ingest_run


async def _single_run(session) -> IngestRun:
    return (await session.execute(select(IngestRun))).scalar_one()


async def test_ok_run(session):
    async with ingest_run(session, "job_a", "kite", date(2026, 7, 30)) as rec:
        rec.add_rows(42)
    run = await _single_run(session)
    assert run.status == "OK"
    assert run.rows_written == 42
    assert run.finished_at is not None


async def test_partial_run_on_symbol_error(session):
    async with ingest_run(session, "job_a", "kite", date(2026, 7, 30)) as rec:
        rec.add_rows(10)
        rec.record_error("BADSYM", "TimeoutError()")
    run = await _single_run(session)
    assert run.status == "PARTIAL"
    errors = run.errors if isinstance(run.errors, dict) else json.loads(run.errors)
    assert errors == {"BADSYM": "TimeoutError()"}


async def test_failed_run_reraises_and_records(session):
    with pytest.raises(RuntimeError):
        async with ingest_run(session, "job_a", "kite", date(2026, 7, 30)) as rec:
            rec.add_rows(5)
            raise RuntimeError("source down")
    run = await _single_run(session)
    assert run.status == "FAILED"
    assert run.finished_at is not None
