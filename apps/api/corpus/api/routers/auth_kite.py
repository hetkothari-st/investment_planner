"""Kite login flow: /auth/kite/login redirects to Kite; the callback exchanges
request_token -> access_token and stores it in Redis until the next 06:00 IST."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from kiteconnect.exceptions import KiteException
from pydantic import BaseModel
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from corpus.config import get_settings
from corpus.ingest.kite import auth

router = APIRouter(prefix="/auth/kite", tags=["auth"])


def _redis() -> Redis:
    return Redis.from_url(get_settings().redis_url)


@router.get("/login")
async def login() -> RedirectResponse:
    if not get_settings().kite_api_key:
        raise HTTPException(status_code=503, detail="KITE_API_KEY is not configured")
    return RedirectResponse(auth.login_url())


class AuthStatus(BaseModel):
    authenticated: bool
    degraded_reason: str | None


@router.get("/callback")
async def callback(request_token: str) -> AuthStatus:
    redis = _redis()
    try:
        await auth.exchange_and_store(request_token, redis)
    except KiteException as exc:
        await auth.mark_degraded(redis, f"Token exchange failed: {exc}")
        raise HTTPException(status_code=502, detail=f"Kite token exchange failed: {exc}") from exc
    finally:
        await redis.aclose()
    return AuthStatus(authenticated=True, degraded_reason=None)


@router.get("/status")
async def status() -> AuthStatus:
    redis = _redis()
    try:
        token = await auth.get_access_token(redis)
        reason = await auth.degraded_reason(redis)
    except RedisConnectionError as exc:
        raise HTTPException(
            status_code=503,
            detail="Redis is unreachable. Start it (docker compose up redis) and retry.",
        ) from exc
    finally:
        await redis.aclose()
    return AuthStatus(authenticated=token is not None, degraded_reason=reason)
