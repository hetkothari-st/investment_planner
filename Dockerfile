# CORPUS — single-image deployment (Railway): FastAPI serves the API under
# /api and the built web bundle at /. Postgres and Redis are separate
# managed services; see docs/DEPLOY-RAILWAY.md.

# --- stage 1: web bundle ----------------------------------------------------
FROM node:22-slim AS web
WORKDIR /repo
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/contracts/package.json packages/contracts/package.json
RUN pnpm install --frozen-lockfile
COPY apps/web apps/web
COPY packages/contracts packages/contracts
RUN pnpm --filter web build

# --- stage 2: runtime -------------------------------------------------------
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
# keep the repo shape: config loaders resolve repo_root/config relative to
# the package path (apps/api/corpus/... -> /app/config)
COPY config config
COPY docs docs
COPY apps/api apps/api

WORKDIR /app/apps/api
RUN uv sync --frozen --no-dev

COPY --from=web /repo/apps/web/dist /app/web-dist
ENV CORPUS_WEB_DIST=/app/web-dist

# Railway injects PORT; migrations run before serving so the schema is
# always current with the image
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn corpus.api.prod:app --host 0.0.0.0 --port ${PORT:-8000}"]
