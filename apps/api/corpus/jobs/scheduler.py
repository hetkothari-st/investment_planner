"""The nightly pipeline on a clock — docs/01, post-close 16:15 IST.

Runs the steps that exist today (8-11: falsifier check, position marks,
recommendation scoring; calibration summaries are computed on read). The
ingest steps (1-5) join this job as their sources come online — each run
records an ingest_run row per step, so "data current as of" stays honest
even about what did not run.

Enabled with CORPUS_SCHEDULER=1; off by default so tests and one-off
scripts never sprout background jobs.
"""

import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from corpus.db.session import get_sessionmaker
from corpus.ingest.runs import ingest_run
from corpus.sim.calibration import score_expired_recommendations
from corpus.sim.falsifiers import check_falsifiers
from corpus.sim.positions import mark_open_positions

log = logging.getLogger("corpus.jobs")

IST = "Asia/Kolkata"


async def nightly_pipeline() -> dict[str, str]:
    """Steps run in docs/01 order; a failed step is recorded and does not
    silently take the later steps down with it."""
    today = datetime.now(UTC).date()
    results: dict[str, str] = {}
    maker = get_sessionmaker()

    async def step(name: str, fn) -> None:
        async with maker() as session:
            try:
                # ingest_run sets status and commits on exit, success or not
                async with ingest_run(session, f"pipeline:{name}", "scheduler", today) as rec:
                    detail = await fn(session)
                    rec.add_rows(detail if isinstance(detail, int) else 0)
                results[name] = "OK"
            except Exception as exc:
                results[name] = f"FAILED: {exc!r}"
                log.exception("nightly step %s failed", name)

    async def _falsifiers(session) -> int:
        report = await check_falsifiers(session, today)
        return report.breached

    async def _marks(session) -> int:
        return await mark_open_positions(session, today)

    async def _scoring(session) -> int:
        scored, _skipped = await score_expired_recommendations(session, today)
        return scored

    await step("check_falsifiers", _falsifiers)
    await step("mark_simulated_positions", _marks)
    await step("score_expired_recommendations", _scoring)
    log.info("nightly pipeline: %s", results)
    return results


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=IST)
    scheduler.add_job(
        nightly_pipeline,
        CronTrigger(hour=16, minute=15, timezone=IST),
        id="nightly_pipeline",
        coalesce=True,  # a missed night runs once, not N times
        misfire_grace_time=3600 * 6,
    )
    return scheduler
