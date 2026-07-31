"""The in-process live hub: one upstream feed, many browser websockets.

The reconnect loop IS the acceptance criterion (docs/10 M9): the browser's
session survives upstream drops because the browser is never connected to
the upstream — it is connected to this hub, which reconnects with capped
exponential backoff and tells clients honestly what state the feed is in.
"""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from corpus.live.feed import FeedError, Tick

BACKOFF_S = (1.0, 2.0, 4.0, 8.0, 15.0, 30.0)  # capped; resets on a good tick


def backoff_delay(attempt: int) -> float:
    return BACKOFF_S[min(attempt, len(BACKOFF_S) - 1)]


@dataclass
class HubState:
    status: str = "DISCONNECTED"  # DISCONNECTED | CONNECTING | CONNECTED | RECONNECTING
    reconnects: int = 0
    last_tick_at: datetime | None = None
    last_error: str | None = None


class LiveHub:
    def __init__(
        self,
        feed_factory: Callable[[], Any],
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        queue_size: int = 500,
    ) -> None:
        self.feed_factory = feed_factory
        self.sleep = sleep
        self.queue_size = queue_size
        self.state = HubState()
        self.snapshot: dict[int, Tick] = {}
        self.clients: set[asyncio.Queue] = set()
        self._task: asyncio.Task | None = None

    # --- client side -----------------------------------------------------

    def attach(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=self.queue_size)
        self.clients.add(q)
        return q

    def detach(self, q: asyncio.Queue) -> None:
        self.clients.discard(q)

    def _broadcast(self, message: dict) -> None:
        for q in list(self.clients):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                # a stalled client loses frames, not the hub; the snapshot
                # heals it on the next state message it does read
                with contextlib.suppress(asyncio.QueueEmpty):
                    q.get_nowait()
                with contextlib.suppress(asyncio.QueueFull):
                    q.put_nowait(message)

    @staticmethod
    def tick_payload(tick: Tick) -> dict:
        return {
            "type": "tick",
            "instrument_token": tick.instrument_token,
            "last_price": str(tick.last_price),
            "change_pct": None if tick.change_pct is None else str(tick.change_pct),
            "received_at": tick.received_at.isoformat(),
        }

    def state_payload(self) -> dict:
        return {
            "type": "state",
            "status": self.state.status,
            "reconnects": self.state.reconnects,
            "last_tick_at": (
                self.state.last_tick_at.isoformat() if self.state.last_tick_at else None
            ),
        }

    # --- upstream side ----------------------------------------------------

    def _set_status(self, status: str, error: str | None = None) -> None:
        self.state.status = status
        self.state.last_error = error
        self._broadcast(self.state_payload())

    async def _on_tick(self, tick: Tick) -> None:
        self.snapshot[tick.instrument_token] = tick
        self.state.last_tick_at = tick.received_at
        if self.state.status != "CONNECTED":
            self._set_status("CONNECTED")
        self._broadcast(self.tick_payload(tick))

    async def run(self) -> None:
        attempt = 0
        while True:
            try:
                self._set_status("CONNECTING" if attempt == 0 else "RECONNECTING")
                feed = self.feed_factory()
                before = self.state.last_tick_at
                await feed.run(self._on_tick)
            except asyncio.CancelledError:
                self._set_status("DISCONNECTED")
                raise
            except FeedError as exc:
                if self.state.last_tick_at is not None and self.state.last_tick_at != before:
                    attempt = 0  # the connection worked; start backoff fresh
                self.state.reconnects += 1
                self._set_status("RECONNECTING", error=str(exc))
                await self.sleep(backoff_delay(attempt))
                attempt += 1

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(self.run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        # cancellation can land in the backoff sleep, outside run()'s own
        # CancelledError handler — the final state is set here either way
        self._set_status("DISCONNECTED")


@dataclass
class HubRegistry:
    """App-level singleton holder so tests can swap the hub cleanly."""

    hub: LiveHub | None = None
    kind: str = "off"
    detail: str = ""
    extra: dict = field(default_factory=dict)


registry = HubRegistry()
