import asyncio

from src.config import NICHE_SUBREDDITS, settings
from src.ingest.base import HTTPSource, RawSignal, SourceUnavailable

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
OAUTH_BASE = "https://oauth.reddit.com"

# Reddit allows 60 req/min for OAuth clients; ~1.1s between subreddit calls
# keeps us safely under it.
REQUEST_INTERVAL_S = 1.1


class RedditSource(HTTPSource):
    name = "reddit"

    async def _get_token(self) -> str:
        payload = await self._request(
            "POST",
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(settings.reddit_client_id, settings.reddit_client_secret),
            headers={"User-Agent": settings.reddit_user_agent},
        )
        token = payload.get("access_token")
        if not token:
            raise SourceUnavailable(f"reddit: no access_token in response: {payload}")
        return token

    async def fetch(self) -> list[RawSignal]:
        if not (settings.reddit_client_id and settings.reddit_client_secret):
            raise SourceUnavailable("reddit: REDDIT_CLIENT_ID/SECRET not set")

        token = await self._get_token()
        headers = {
            "Authorization": f"bearer {token}",
            "User-Agent": settings.reddit_user_agent,
        }

        signals: list[RawSignal] = []
        for niche, subs in NICHE_SUBREDDITS.items():
            for sub in subs:
                payload = await self._request(
                    "GET",
                    f"{OAUTH_BASE}/r/{sub}/rising.json",
                    params={"limit": 50},
                    headers=headers,
                )
                for child in payload.get("data", {}).get("children", []):
                    post = child.get("data", {})
                    title = post.get("title")
                    if not title:
                        continue
                    signals.append(
                        RawSignal(
                            external_id=post["id"],
                            topic_raw=title,
                            metric_value=float(post.get("score", 0)),
                            niche=niche,
                            raw={
                                "subreddit": sub,
                                "title": title,
                                "score": post.get("score"),
                                "num_comments": post.get("num_comments"),
                                "upvote_ratio": post.get("upvote_ratio"),
                                "created_utc": post.get("created_utc"),
                                "permalink": post.get("permalink"),
                            },
                        )
                    )
                await asyncio.sleep(REQUEST_INTERVAL_S)
        return signals
