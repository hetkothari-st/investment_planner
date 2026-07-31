"""Build the LiveHub from environment config. CORPUS_FEED selects the
upstream: replay (deterministic demo), hub (WS_HUB_URL relay), kite
(KiteTicker with the day's Redis-stored token), off (default).

Whatever the choice, /live/status says what is running and why — an
unconfigured feed is a stated fact, not a blank screen."""

import os

from corpus.config import get_settings
from corpus.live.feed import (
    INDEX_TOKENS,
    FeedError,
    HubFeed,
    KiteTickerFeed,
    ReplayFeed,
    feed_kind,
    replay_seed,
)
from corpus.live.hub import LiveHub, registry


class KiteFromRedisFeed:
    """Fetches the day's access token at connect time, so a re-login during
    the session is picked up by the next reconnect attempt."""

    def __init__(self, tokens: list[int]) -> None:
        self.tokens = tokens

    async def run(self, on_tick) -> None:
        from redis.asyncio import Redis

        from corpus.ingest.kite import auth

        settings = get_settings()
        redis = Redis.from_url(settings.redis_url)
        try:
            access_token = await auth.get_access_token(redis)
        finally:
            await redis.aclose()
        if not access_token:
            raise FeedError("kite: no access token — login via /auth/kite/login")
        feed = KiteTickerFeed(settings.kite_api_key, access_token, self.tokens)
        await feed.run(on_tick)


def configure_hub() -> None:
    kind = feed_kind()
    registry.kind = kind
    registry.hub = None
    if kind == "off":
        registry.detail = (
            "Live feed is off (CORPUS_FEED=off). Set CORPUS_FEED=kite after the "
            "Kite login, or CORPUS_FEED=hub with WS_HUB_URL, or replay for a demo."
        )
        return
    if kind == "replay":
        registry.detail = "Deterministic replay feed — demo data, not the market."
        registry.hub = LiveHub(
            lambda: ReplayFeed(
                replay_seed(),
                interval_s=float(os.environ.get("CORPUS_REPLAY_INTERVAL_S", "2.0")),
                drop_after=(
                    int(v) if (v := os.environ.get("CORPUS_REPLAY_DROP_AFTER")) else None
                ),
            )
        )
        return
    if kind == "hub":
        url = os.environ.get("WS_HUB_URL", "")
        if not url:
            registry.detail = "CORPUS_FEED=hub but WS_HUB_URL is not set."
            return
        registry.detail = f"Upstream hub: {url}"
        subscribe = os.environ.get("WS_HUB_SUBSCRIBE") or None
        registry.hub = LiveHub(lambda: HubFeed(url, subscribe))
        return
    if kind == "kite":
        if not get_settings().kite_api_key:
            registry.detail = "CORPUS_FEED=kite but KITE_API_KEY is not configured."
            return
        registry.detail = "KiteTicker upstream (token from the daily login)."
        tokens = list(INDEX_TOKENS)
        registry.hub = LiveHub(lambda: KiteFromRedisFeed(tokens))
        return
    registry.detail = f"Unknown CORPUS_FEED value {kind!r}; feed stays off."
