import logging

from src.ingest.base import HTTPSource, RawSignal, SourceUnavailable

logger = logging.getLogger(__name__)

# TikTok Creative Center trending-hashtag endpoint. This is UNDOCUMENTED and its
# shape has not been verified live from this environment — it can change or start
# requiring extra headers/tokens at any time. Per spec §5, any failure here is
# non-fatal: the runner logs and continues with the other sources.
HASHTAG_URL = (
    "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list"
)


class TikTokCreativeCenterSource(HTTPSource):
    name = "tiktok_cc"

    async def fetch(self) -> list[RawSignal]:
        try:
            payload = await self._request(
                "GET",
                HASHTAG_URL,
                params={"page": 1, "limit": 50, "period": 7, "country_code": "IN"},
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
                    ),
                    "Referer": "https://ads.tiktok.com/business/creativecenter/",
                },
            )
        except SourceUnavailable:
            raise
        except Exception as exc:
            raise SourceUnavailable(f"tiktok_cc: {exc}") from exc

        items = (payload or {}).get("data", {}).get("list", [])
        if not isinstance(items, list):
            raise SourceUnavailable(f"tiktok_cc: unexpected payload shape: {type(items)}")

        signals: list[RawSignal] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("hashtag_name") or item.get("keyword")
            if not name:
                continue
            hashtag_id = str(item.get("hashtag_id") or name)
            metric = item.get("publish_cnt") or item.get("video_views")
            signals.append(
                RawSignal(
                    external_id=hashtag_id,
                    topic_raw=name,
                    metric_value=float(metric) if metric is not None else None,
                    raw={
                        "hashtag_name": name,
                        "publish_cnt": item.get("publish_cnt"),
                        "video_views": item.get("video_views"),
                        "rank": item.get("rank"),
                        "trend": item.get("trend"),
                    },
                )
            )
        return signals
