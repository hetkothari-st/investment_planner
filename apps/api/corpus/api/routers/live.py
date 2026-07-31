"""Live routes: the browser-facing websocket (docs/02: credentials never
reach the browser — the browser only ever connects here), feed status,
indices and movers from the hub's snapshot."""

import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from corpus.db.models import Instrument
from corpus.db.session import get_session
from corpus.live.feed import INDEX_TOKENS, REPLAY_SYMBOLS
from corpus.live.hub import registry

router = APIRouter(prefix="/live", tags=["live"])

HEARTBEAT_S = 15.0


@router.websocket("/ws")
async def live_ws(ws: WebSocket) -> None:
    """Snapshot first, then ticks and state changes as they happen; a
    heartbeat every 15s so a silent feed is distinguishable from a dead
    socket. The upstream reconnect loop lives server-side — a feed drop
    changes the state frames, never this connection."""
    await ws.accept()
    hub = registry.hub
    if hub is None:
        await ws.send_json(
            {"type": "state", "status": "OFF", "reconnects": 0, "detail": registry.detail}
        )
        await ws.close()
        return
    q = hub.attach()
    receiver = asyncio.create_task(ws.receive_text())  # completes on disconnect
    try:
        await ws.send_json(
            {
                "type": "snapshot",
                "state": hub.state_payload(),
                "detail": registry.detail,
                "ticks": [hub.tick_payload(t) for _, t in sorted(hub.snapshot.items())],
            }
        )
        while True:
            getter = asyncio.create_task(q.get())
            done, _ = await asyncio.wait(
                {getter, receiver},
                timeout=HEARTBEAT_S,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if receiver in done:
                getter.cancel()
                receiver.exception()  # retrieve the disconnect, silence the warning
                break
            if getter in done:
                await ws.send_json(getter.result())
            else:
                getter.cancel()
                await ws.send_json({"type": "heartbeat"})
    except (WebSocketDisconnect, RuntimeError):
        pass  # client went away mid-send; nothing to clean up but the queue
    finally:
        receiver.cancel()
        hub.detach(q)


class LiveStatus(BaseModel):
    feed: str
    detail: str
    status: str
    reconnects: int
    last_tick_at: datetime | None
    tracked: int
    clients: int


@router.get("/status")
async def live_status() -> LiveStatus:
    hub = registry.hub
    if hub is None:
        return LiveStatus(
            feed=registry.kind, detail=registry.detail, status="OFF",
            reconnects=0, last_tick_at=None, tracked=0, clients=0,
        )
    return LiveStatus(
        feed=registry.kind,
        detail=registry.detail,
        status=hub.state.status,
        reconnects=hub.state.reconnects,
        last_tick_at=hub.state.last_tick_at,
        tracked=len(hub.snapshot),
        clients=len(hub.clients),
    )


class QuoteOut(BaseModel):
    instrument_token: int
    symbol: str
    last_price: str
    change_pct: str | None
    received_at: datetime


class MarketOverview(BaseModel):
    feed: str
    status: str
    indices: list[QuoteOut]
    gainers: list[QuoteOut]
    losers: list[QuoteOut]
    message: str | None


async def _symbols(session: AsyncSession, tokens: list[int]) -> dict[int, str]:
    if not tokens:
        return {}
    rows = (
        await session.execute(
            select(Instrument.instrument_token, Instrument.tradingsymbol).where(
                Instrument.instrument_token.in_(tokens)
            )
        )
    ).all()
    found = {r.instrument_token: r.tradingsymbol for r in rows}
    return {
        t: found.get(t) or INDEX_TOKENS.get(t) or REPLAY_SYMBOLS.get(t) or str(t)
        for t in tokens
    }


@router.get("/overview")
async def market_overview(
    session: AsyncSession = Depends(get_session),
) -> MarketOverview:
    hub = registry.hub
    if hub is None or not hub.snapshot:
        return MarketOverview(
            feed=registry.kind,
            status=registry.hub.state.status if registry.hub else "OFF",
            indices=[], gainers=[], losers=[],
            message=registry.detail or "No live data yet.",
        )
    names = await _symbols(session, list(hub.snapshot))
    quotes = {
        token: QuoteOut(
            instrument_token=token,
            symbol=names[token],
            last_price=str(t.last_price),
            change_pct=None if t.change_pct is None else str(t.change_pct),
            received_at=t.received_at,
        )
        for token, t in hub.snapshot.items()
    }
    indices = [quotes[t] for t in INDEX_TOKENS if t in quotes]
    stocks = sorted(
        (q for t, q in quotes.items() if t not in INDEX_TOKENS and q.change_pct),
        key=lambda q: float(q.change_pct or 0),
    )
    return MarketOverview(
        feed=registry.kind,
        status=hub.state.status,
        indices=indices,
        gainers=list(reversed(stocks[-5:])),
        losers=stocks[:5],
        message=None,
    )
