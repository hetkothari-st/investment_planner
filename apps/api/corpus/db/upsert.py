"""Change-detecting upsert.

INSERT ... ON CONFLICT DO UPDATE, but the UPDATE only fires when a value
actually differs. Re-running a day over identical data therefore changes zero
rows — which is how ingest idempotency is proved (docs/10, M1 acceptance).

Postgres in production; the SQLite branch exists solely so the idempotency
tests can run without a server.
"""

from typing import Any

from sqlalchemy import Table, tuple_
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession


async def upsert_rows(
    session: AsyncSession,
    table: Table,
    rows: list[dict[str, Any]],
    key_cols: list[str],
    skip_update_cols: tuple[str, ...] = ("ingested_at", "updated_at"),
) -> int:
    """Insert or update rows; returns the number of rows actually written."""
    if not rows:
        return 0

    dialect = session.bind.dialect.name
    insert_fn = postgresql.insert if dialect == "postgresql" else sqlite.insert
    stmt = insert_fn(table).values(rows)

    update_cols = [
        c.name
        for c in table.columns
        if c.name not in key_cols and c.name not in skip_update_cols
    ]
    changed = tuple_(*[table.c[c] for c in update_cols]).is_distinct_from(
        tuple_(*[stmt.excluded[c] for c in update_cols])
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=key_cols,
        set_={c: stmt.excluded[c] for c in update_cols},
        where=changed,
    )
    result = await session.execute(stmt)
    return result.rowcount if result.rowcount is not None and result.rowcount > 0 else 0
