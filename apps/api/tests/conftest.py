import os

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from corpus.db.base import Base

PG_URL = os.environ.get("CORPUS_TEST_PG_URL")


@pytest.fixture
async def session():
    """DB session with the full schema.

    Runs on in-memory SQLite by default so the suite needs no server; when
    CORPUS_TEST_PG_URL is set (CI, local acceptance runs) the same tests run
    against real Postgres, which exercises the production upsert dialect.
    """
    engine = create_async_engine(PG_URL or "sqlite+aiosqlite://")
    async with engine.begin() as conn:
        if PG_URL:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    if PG_URL:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
