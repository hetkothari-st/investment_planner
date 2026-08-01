import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class RawSignal(BaseModel):
    external_id: str
    topic_raw: str
    metric_value: float | None = None
    raw: dict
    # Set when the source itself determines the niche (e.g. per-niche subreddit
    # lists). Left None for sources that need LLM classification.
    niche: str | None = None


class SourceUnavailable(Exception):
    """Raised when a source cannot produce signals this run (missing key, API down).

    The runner treats this as non-fatal: log and continue with other sources.
    """


class TrendSource(ABC):
    name: str

    @abstractmethod
    async def fetch(self) -> list[RawSignal]: ...


class HTTPSource(TrendSource):
    """Base for sources backed by an HTTP API. All external calls go through
    _request(), which applies timeout, retry with exponential backoff, and
    rate-limit (429) handling. No requests.get scattered through business logic.
    """

    max_retries = 3
    timeout_s = 20.0

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        data: dict[str, Any] | None = None,
        auth: tuple[str, str] | None = None,
    ) -> Any:
        backoff = 2.0
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    resp = await client.request(
                        method, url, params=params, headers=headers, data=data, auth=auth
                    )
                    if resp.status_code in RETRYABLE_STATUS:
                        retry_after = resp.headers.get("retry-after")
                        wait = float(retry_after) if retry_after else backoff
                        if attempt < self.max_retries:
                            logger.warning(
                                "%s: HTTP %s from %s, retrying in %.1fs",
                                self.name, resp.status_code, url, wait,
                            )
                            await asyncio.sleep(wait)
                            backoff *= 2
                            continue
                        raise SourceUnavailable(
                            f"{self.name}: HTTP {resp.status_code} after retries"
                        )
                    resp.raise_for_status()
                    return resp.json()
                except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                    last_error = exc
                    if attempt < self.max_retries:
                        await asyncio.sleep(backoff)
                        backoff *= 2
                        continue
        raise SourceUnavailable(f"{self.name}: {last_error}")
