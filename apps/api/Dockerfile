# Dev container for the API. Build context is the REPO ROOT (set in
# docker-compose.yml): the versioned config/ directory lives at the repo
# root and the loaders resolve it relative to the package path, so the
# repo shape must be preserved inside the image.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY config config
COPY docs docs
COPY apps/api apps/api

WORKDIR /app/apps/api
RUN uv sync --frozen --no-dev

EXPOSE 8000
# migrations first, so a fresh database is ready on first boot
CMD ["sh", "-c", "uv run --no-sync alembic upgrade head && uv run --no-sync uvicorn corpus.api.main:app --host 0.0.0.0 --port 8000 --reload"]
