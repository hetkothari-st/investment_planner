"""The deployed shape: one process serving the API under /api and the built
web bundle at / (SPA fallback to index.html).

The paths mirror dev exactly — the web bundle already calls `/api/...`, and
vite's dev proxy rewrote that prefix; here the mount does. The live
websocket rides the same mount at /api/live/ws.

Auth: CLAUDE.md says single-user, no auth beyond a local session — but a
public deployment is not a local session. When CORPUS_BASIC_AUTH is set
("user:password"), every request outside /api/health — websocket upgrades
included — must carry HTTP Basic credentials. When it is unset the app
refuses to serve anything but the health check, loudly: an unprotected
internet-facing deployment must be an explicit choice
(CORPUS_BASIC_AUTH=off), never a default.
"""

import base64
import os
import secrets
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException  # StaticFiles raises this parent class

from corpus.api.main import create_app, lifespan


class SpaStaticFiles(StaticFiles):
    """Client-side routes (/planner, /alerts, ...) fall back to index.html;
    real missing assets (anything with an extension) still 404. Starlette
    raises HTTPException for missing files, so catch rather than inspect."""

    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code == 404 and "." not in path.rsplit("/", 1)[-1]:
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404 and "." not in path.rsplit("/", 1)[-1]:
            return await super().get_response("index.html", scope)
        return response


def _authorized(scope, expected: str) -> bool:
    header = next(
        (v for k, v in scope.get("headers", []) if k == b"authorization"), b""
    ).decode("latin-1")
    if not header.startswith("Basic "):
        return False
    try:
        supplied = base64.b64decode(header[6:]).decode()
    except Exception:
        return False
    return secrets.compare_digest(supplied, expected)


class BasicAuthASGI:
    """Pure ASGI so websocket upgrades are covered, not just HTTP."""

    def __init__(self, app, credentials: str) -> None:
        self.app = app
        self.credentials = credentials

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] not in ("http", "websocket") or scope["path"] == "/api/health":
            return await self.app(scope, receive, send)
        if self.credentials == "off":
            return await self.app(scope, receive, send)

        async def deny(status: int, body: bytes, headers: list) -> None:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 4401})
                return
            await send({"type": "http.response.start", "status": status, "headers": headers})
            await send({"type": "http.response.body", "body": body})

        if not self.credentials:
            return await deny(
                503,
                b"CORPUS_BASIC_AUTH is not set. Set it to user:password, or "
                b"explicitly to 'off' to run this deployment unprotected.",
                [(b"content-type", b"text/plain")],
            )
        if _authorized(scope, self.credentials):
            return await self.app(scope, receive, send)
        return await deny(
            401, b"", [(b"www-authenticate", b'Basic realm="corpus"')]
        )


def create_prod_app():
    # the outer app owns the lifespan: Starlette does not run lifespans of
    # mounted sub-apps, so the hub/scheduler start here
    outer = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    outer.mount("/api", create_app())
    dist = Path(os.environ.get("CORPUS_WEB_DIST", "/app/web-dist"))
    if dist.is_dir():
        outer.mount("/", SpaStaticFiles(directory=dist, html=True), name="web")
    return BasicAuthASGI(outer, os.environ.get("CORPUS_BASIC_AUTH", ""))


app = create_prod_app()
