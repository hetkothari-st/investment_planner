"""M9 acceptance, compressed: the hub survives a session with repeated
upstream drops — reconnect on every drop, ticks resume, clients keep one
uninterrupted connection. Timescale is compressed (the backoff sleep is
injected); the code path is the production one, not a mock of it."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from corpus.live.feed import FeedError, HubFeed, ReplayFeed
from corpus.live.hub import BACKOFF_S, LiveHub, backoff_delay

D = Decimal


async def fast_sleep(_s: float) -> None:
    await asyncio.sleep(0)


def make_hub(drop_after: int | None = 5) -> LiveHub:
    return LiveHub(
        feed_factory=lambda: ReplayFeed(
            {256265: D("24820"), 738561: D("2841.10")},
            interval_s=0.0,
            drop_after=drop_after,
        ),
        sleep=fast_sleep,
    )


async def drain(q: asyncio.Queue, n: int, timeout: float = 5.0) -> list[dict]:
    out = []
    async with asyncio.timeout(timeout):
        while len(out) < n:
            out.append(await q.get())
    return out


async def test_session_survives_repeated_upstream_drops():
    """The 30-minute criterion, compressed: a client stays attached across
    many upstream drops; ticks keep flowing and every drop is a counted,
    visible reconnect — never a client disconnect."""
    hub = make_hub(drop_after=5)
    hub.start()
    try:
        q = hub.attach()
        # each connect cycle = 5 ticks + 3 state frames; 400 messages ≈ 50 drops
        messages = await drain(q, 400)
        ticks = [m for m in messages if m["type"] == "tick"]
        states = [m for m in messages if m["type"] == "state"]
        assert len(ticks) >= 240
        assert hub.state.reconnects >= 10
        assert any(s["status"] == "RECONNECTING" for s in states)
        assert any(s["status"] == "CONNECTED" for s in states)
        # the client was never detached — same queue, still registered
        assert q in hub.clients
    finally:
        await hub.stop()
    assert hub.state.status == "DISCONNECTED"


async def test_backoff_resets_after_a_working_connection():
    delays: list[float] = []

    async def spy_sleep(s: float) -> None:
        delays.append(s)

    hub = LiveHub(
        feed_factory=lambda: ReplayFeed({1: D("100")}, interval_s=0.0, drop_after=3),
        sleep=spy_sleep,
    )
    hub.start()
    try:
        q = hub.attach()
        await drain(q, 40)
    finally:
        await hub.stop()
    # every connection delivered ticks before dropping, so attempt resets
    # each time and the delay never escalates past the first rung
    assert delays and all(d == BACKOFF_S[0] for d in delays)


def test_backoff_ladder_caps():
    assert [backoff_delay(i) for i in range(8)] == [1, 2, 4, 8, 15, 30, 30, 30]


async def test_dead_upstream_escalates_backoff():
    class DeadFeed:
        async def run(self, on_tick) -> None:
            raise FeedError("refused")

    delays: list[float] = []

    async def spy_sleep(s: float) -> None:
        delays.append(s)
        if len(delays) >= 6:
            raise asyncio.CancelledError  # stop the loop from inside

    hub = LiveHub(feed_factory=DeadFeed, sleep=spy_sleep)
    task = asyncio.get_running_loop().create_task(hub.run())
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert delays == [1, 2, 4, 8, 15, 30]


async def test_slow_client_loses_frames_not_the_hub():
    hub = make_hub(drop_after=None)
    hub.queue_size = 4
    hub.start()
    try:
        stalled = hub.attach()  # never drained
        healthy = hub.attach()
        got = await drain(healthy, 30)
        assert len(got) == 30
        assert stalled.qsize() <= 4  # bounded, oldest dropped
    finally:
        await hub.stop()


def test_hub_feed_parsing_is_tolerant():
    ts = datetime.now(UTC)
    assert HubFeed.parse("not json") == []
    assert HubFeed.parse('{"hello": 1}') == []
    one = HubFeed.parse('{"instrument_token": 256265, "last_price": "24820.5"}')
    assert one[0].instrument_token == 256265 and one[0].last_price == D("24820.5")
    many = HubFeed.parse(
        '{"ticks": [{"token": 1, "ltp": 10, "chg": "-0.4"}, {"token": 2, "price": 20}]}'
    )
    assert [t.instrument_token for t in many] == [1, 2]
    assert many[0].change_pct == D("-0.4") and many[1].change_pct is None
    assert isinstance(one[0].received_at, type(ts))
