"""Phase 1 checklist: re-running within the same minute produces no
duplicate-key errors — the uq_signal constraint plus ON CONFLICT DO NOTHING
must dedupe. Requires a migrated Postgres at DATABASE_URL; skipped otherwise."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from src.db import SessionLocal
from src.ingest.base import RawSignal
from src.ingest.runner import persist_signals


async def _db_available() -> bool:
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1 FROM trend_signal LIMIT 1"))
        return True
    except Exception:
        return False


@pytest.mark.asyncio
async def test_rerun_same_minute_no_duplicates():
    if not await _db_available():
        pytest.skip("Postgres with migrated schema not available")

    marker = f"test-{uuid.uuid4().hex[:8]}"
    observed_at = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    signals = {
        "synthetic": [
            RawSignal(
                external_id=f"{marker}-{i}",
                topic_raw=f"Synthetic dedup topic {marker} {i}",
                metric_value=float(i),
                niche="facts",
                raw={"marker": marker},
            )
            for i in range(5)
        ]
    }

    first = await persist_signals(signals, observed_at)
    second = await persist_signals(signals, observed_at)

    assert first == 5
    assert second == 0

    async with SessionLocal() as session:
        count = (
            await session.execute(
                text(
                    "SELECT count(*) FROM trend_signal "
                    "WHERE source='synthetic' AND external_id LIKE :m"
                ),
                {"m": f"{marker}%"},
            )
        ).scalar_one()
        await session.execute(
            text(
                "DELETE FROM trend_signal "
                "WHERE source='synthetic' AND external_id LIKE :m"
            ),
            {"m": f"{marker}%"},
        )
        await session.commit()
    assert count == 5
