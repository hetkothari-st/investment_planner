"""ingest_run bookkeeping — every job records started/finished/rows/errors."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from corpus.db.models import IngestRun


class RunRecorder:
    def __init__(self, run: IngestRun) -> None:
        self.run = run
        self.rows_written = 0
        self.errors: dict[str, str] = {}

    def add_rows(self, n: int) -> None:
        self.rows_written += n

    def record_error(self, entity: str, error: str) -> None:
        """One bad symbol must not fail the batch — record and continue."""
        self.errors[entity] = error


@asynccontextmanager
async def ingest_run(
    session: AsyncSession, job: str, source: str, as_of: date
) -> AsyncIterator[RunRecorder]:
    run = IngestRun(job=job, source=source, as_of=as_of, started_at=datetime.now(UTC))
    session.add(run)
    await session.flush()
    recorder = RunRecorder(run)
    try:
        yield recorder
    except Exception as exc:
        run.status = "FAILED"
        recorder.errors["__job__"] = repr(exc)
        raise
    else:
        run.status = "PARTIAL" if recorder.errors else "OK"
    finally:
        run.finished_at = datetime.now(UTC)
        run.rows_written = recorder.rows_written
        if recorder.errors:
            errors = recorder.errors
            if session.bind.dialect.name == "sqlite":
                errors = json.dumps(recorder.errors)  # type: ignore[assignment]
            run.errors = errors
        await session.commit()
