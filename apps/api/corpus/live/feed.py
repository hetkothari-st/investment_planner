"""Upstream live feeds — docs/02: live quotes come through the API,
credentials never reach the browser.

The upstream is pluggable (CORPUS_FEED = hub | kite | replay | off), in the
same spirit as the ingest Source protocol: any one can be swapped without
touching downstream code. The LiveHub (hub.py) wraps whichever feed is
configured in a reconnect loop; a feed's only job is to connect, push ticks,
and raise when the connection dies.
"""

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

OnTick = Callable[["Tick"], Awaitable[None]]


@dataclass(frozen=True)
class Tick:
    instrument_token: int
    last_price: Decimal
    change_pct: Decimal | None  # vs previous close; None when upstream omits it
    received_at: datetime


class FeedError(Exception):
    """Connection failed or dropped. The hub's reconnect loop handles it."""


class ReplayFeed:
    """Deterministic fake upstream for tests, demos and the sandbox.

    Emits a seeded random-walk over the configured tokens. `drop_after`
    raises FeedError after that many ticks — the reconnect path in tests
    and live demos is the real code path, not a mock of it.
    """

    def __init__(
        self,
        tokens: dict[int, Decimal],
        interval_s: float = 1.0,
        drop_after: int | None = None,
    ) -> None:
        self.tokens = dict(tokens)
        self.interval_s = interval_s
        self.drop_after = drop_after
        self._base = dict(tokens)
        self._emitted = 0

    async def run(self, on_tick: OnTick) -> None:
        # deterministic pseudo-walk: no wall-clock, no RNG state to leak
        while True:
            for i, (token, price) in enumerate(sorted(self.tokens.items())):
                if self.drop_after is not None and self._emitted >= self.drop_after:
                    self._emitted = 0
                    raise FeedError("replay feed: simulated connection drop")
                step = Decimal((self._emitted + i) % 7 - 3) / Decimal(400)
                price = (price * (1 + step)).quantize(Decimal("0.05"))
                self.tokens[token] = price
                base = self._base[token]
                change = ((price - base) / base * 100).quantize(Decimal("0.01"))
                await on_tick(
                    Tick(
                        instrument_token=token,
                        last_price=price,
                        change_pct=change,
                        received_at=datetime.now(UTC),
                    )
                )
                self._emitted += 1
            await asyncio.sleep(self.interval_s)


class HubFeed:
    """JSON websocket hub upstream (WS_HUB_URL), e.g. a relay that already
    holds the Kite session server-side.

    Tolerant field mapping until the hub's exact schema is pinned down:
    token from instrument_token|token, price from last_price|ltp|price,
    change from change_pct|change|chg. Anything unmappable is skipped —
    a malformed message is not a crash. WS_HUB_SUBSCRIBE (JSON) is sent
    once on connect when provided.
    """

    def __init__(self, url: str, subscribe_json: str | None = None) -> None:
        self.url = url
        self.subscribe_json = subscribe_json

    @staticmethod
    def parse(raw: str | bytes) -> list[Tick]:
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return []
        items = payload if isinstance(payload, list) else [payload]
        if isinstance(payload, dict) and isinstance(payload.get("ticks"), list):
            items = payload["ticks"]
        out: list[Tick] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            token = item.get("instrument_token", item.get("token"))
            price = item.get("last_price", item.get("ltp", item.get("price")))
            change = item.get("change_pct", item.get("change", item.get("chg")))
            if token is None or price is None:
                continue
            try:
                out.append(
                    Tick(
                        instrument_token=int(token),
                        last_price=Decimal(str(price)),
                        change_pct=None if change is None else Decimal(str(change)),
                        received_at=datetime.now(UTC),
                    )
                )
            except (ValueError, ArithmeticError):
                continue
        return out

    async def run(self, on_tick: OnTick) -> None:
        import websockets

        try:
            async with websockets.connect(self.url, ping_interval=15) as ws:
                if self.subscribe_json:
                    await ws.send(self.subscribe_json)
                async for raw in ws:
                    for tick in self.parse(raw):
                        await on_tick(tick)
        except Exception as exc:  # websockets exception zoo -> one class
            raise FeedError(f"hub feed: {exc}") from exc
        raise FeedError("hub feed: upstream closed the stream")


class KiteTickerFeed:
    """KiteTicker upstream — the direct path from docs/02. Needs
    KITE_API_KEY plus the day's access token from Redis (auth_kite flow).
    The threaded ticker pushes into the event loop; the browser only ever
    sees our own /live/ws frames."""

    def __init__(self, api_key: str, access_token: str, tokens: list[int]) -> None:
        self.api_key = api_key
        self.access_token = access_token
        self.tokens = tokens

    async def run(self, on_tick: OnTick) -> None:
        from kiteconnect import KiteTicker

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Tick | None] = asyncio.Queue(maxsize=1000)
        ticker = KiteTicker(self.api_key, self.access_token)

        def push(tick: Tick | None) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, tick)

        def on_ticks(_ws, ticks) -> None:  # noqa: ANN001 - kiteconnect callback
            for t in ticks:
                price = t.get("last_price")
                if price is None:
                    continue
                push(
                    Tick(
                        instrument_token=t["instrument_token"],
                        last_price=Decimal(str(price)),
                        change_pct=(
                            Decimal(str(t["change"])) if t.get("change") is not None else None
                        ),
                        received_at=datetime.now(UTC),
                    )
                )

        def on_connect(ws, _resp) -> None:  # noqa: ANN001
            ws.subscribe(self.tokens)
            ws.set_mode(ws.MODE_QUOTE, self.tokens)

        def on_close(_ws, _code, _reason) -> None:  # noqa: ANN001
            push(None)

        ticker.on_ticks = on_ticks
        ticker.on_connect = on_connect
        ticker.on_close = on_close
        ticker.connect(threaded=True)
        try:
            while True:
                tick = await queue.get()
                if tick is None:
                    raise FeedError("kite ticker: connection closed")
                await on_tick(tick)
        finally:
            ticker.close()


#: NSE index instrument tokens (Kite conventions) used by the demo/live strip.
INDEX_TOKENS: dict[int, str] = {
    256265: "NIFTY 50",
    260105: "NIFTY BANK",
    257801: "NIFTY MIDCAP 100",
}


def replay_seed() -> dict[int, Decimal]:
    return {
        256265: Decimal("24820.00"),
        260105: Decimal("54130.00"),
        257801: Decimal("57420.00"),
        408065: Decimal("1523.40"),  # a few "stocks" for the movers panel
        738561: Decimal("2841.10"),
        2953217: Decimal("3510.75"),
        341249: Decimal("1655.20"),
        1270529: Decimal("612.35"),
    }


REPLAY_SYMBOLS: dict[int, str] = {
    408065: "INFY",
    738561: "RELIANCE",
    2953217: "TCS",
    341249: "HDFCBANK",
    1270529: "ONGC",
}


def feed_kind() -> str:
    return os.environ.get("CORPUS_FEED", "off").lower()
