from src.config import settings
from src.ingest.base import HTTPSource, RawSignal, SourceUnavailable

API_URL = "https://www.googleapis.com/youtube/v3/videos"


class YouTubeTrendingSource(HTTPSource):
    name = "youtube"

    async def fetch(self) -> list[RawSignal]:
        if not settings.youtube_api_key:
            raise SourceUnavailable("youtube: YOUTUBE_API_KEY not set")

        payload = await self._request(
            "GET",
            API_URL,
            params={
                "part": "snippet,statistics",
                "chart": "mostPopular",
                "regionCode": "IN",
                "maxResults": 50,
                "key": settings.youtube_api_key,
            },
        )

        signals: list[RawSignal] = []
        for item in payload.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            title = snippet.get("title")
            if not title:
                continue
            views = stats.get("viewCount")
            signals.append(
                RawSignal(
                    external_id=item["id"],
                    topic_raw=title,
                    metric_value=float(views) if views is not None else None,
                    raw={
                        "title": title,
                        "channel": snippet.get("channelTitle"),
                        "category_id": snippet.get("categoryId"),
                        "tags": snippet.get("tags", [])[:20],
                        "published_at": snippet.get("publishedAt"),
                        "statistics": stats,
                    },
                )
            )
        return signals
