import json
import logging

import redis.asyncio as aioredis
from anthropic import AsyncAnthropic

from src.config import NICHE_CACHE_TTL_SECONDS, NICHES, settings

logger = logging.getLogger(__name__)

CACHE_PREFIX = "niche:"

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "classifications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "external_id": {"type": "string"},
                    "niche": {
                        "anyOf": [
                            {"type": "string", "enum": NICHES},
                            {"type": "null"},
                        ]
                    },
                },
                "required": ["external_id", "niche"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["classifications"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You classify social-media trend topics from Indian platforms into exactly one "
    f"of these content niches: {', '.join(NICHES)}. If a topic clearly fits none of "
    "them, use null. Classify every topic you are given."
)


async def classify_niches(topics: dict[str, tuple[str, str]]) -> dict[str, str | None]:
    """Classify topics into niches with a SINGLE batched LLM call per ingest run.

    topics maps external_id -> (topic_raw, topic_norm). Returns external_id -> niche|None.
    Results are cached in Redis by topic_norm with a 7-day TTL; only cache misses
    reach the API. Never calls the API per-topic.
    """
    if not topics:
        return {}

    result: dict[str, str | None] = {}
    uncached: dict[str, tuple[str, str]] = {}

    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        norms = [norm for (_, norm) in topics.values()]
        cached = await r.mget([CACHE_PREFIX + n for n in norms])
        cache_by_norm = {
            norm: val for norm, val in zip(norms, cached) if val is not None
        }
        for ext_id, (raw, norm) in topics.items():
            if norm in cache_by_norm:
                val = cache_by_norm[norm]
                result[ext_id] = None if val == "null" else val
            else:
                uncached[ext_id] = (raw, norm)

        if not uncached:
            return result

        if not settings.anthropic_api_key:
            logger.warning(
                "niche: ANTHROPIC_API_KEY not set — %d topics left unclassified",
                len(uncached),
            )
            result.update({ext_id: None for ext_id in uncached})
            return result

        classified = await _classify_batch(uncached)
        pipe = r.pipeline()
        for ext_id, niche in classified.items():
            result[ext_id] = niche
            _, norm = uncached[ext_id]
            pipe.set(
                CACHE_PREFIX + norm,
                niche if niche is not None else "null",
                ex=NICHE_CACHE_TTL_SECONDS,
            )
        await pipe.execute()
        for ext_id in uncached:
            result.setdefault(ext_id, None)
        return result
    finally:
        await r.aclose()


async def _classify_batch(uncached: dict[str, tuple[str, str]]) -> dict[str, str | None]:
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    topic_lines = "\n".join(
        f"{ext_id}\t{raw}" for ext_id, (raw, _) in uncached.items()
    )
    try:
        response = await client.beta.messages.create(
            model=settings.niche_model,
            max_tokens=8192,
            betas=["server-side-fallback-2026-07-01"],
            system=SYSTEM_PROMPT,
            output_config={"format": {"type": "json_schema", "schema": CLASSIFY_SCHEMA}},
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Classify each topic below. One per line: external_id<TAB>topic.\n\n"
                        + topic_lines
                    ),
                }
            ],
            # Server-side refusal fallback ("default" mode); typed SDK support for
            # the scalar form may lag, so it goes over the wire via extra_body.
            extra_body={"fallbacks": "default"},
        )
    except Exception as exc:
        logger.warning("niche: classification call failed (%s) — leaving nulls", exc)
        return {ext_id: None for ext_id in uncached}

    if response.stop_reason == "refusal":
        logger.warning("niche: classification refused — leaving nulls")
        return {ext_id: None for ext_id in uncached}

    text = "".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    )
    try:
        payload = json.loads(text)
        rows = payload["classifications"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("niche: unparseable classification response (%s)", exc)
        return {ext_id: None for ext_id in uncached}

    out: dict[str, str | None] = {}
    for row in rows:
        ext_id = row.get("external_id")
        niche = row.get("niche")
        if ext_id in uncached and (niche in NICHES or niche is None):
            out[ext_id] = niche
    for ext_id in uncached:
        out.setdefault(ext_id, None)
    return out
