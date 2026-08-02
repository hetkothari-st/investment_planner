import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from corpus.api.routers import (
    alerts,
    allocation,
    auth_kite,
    health,
    live,
    planner,
    research,
    sim,
)
from corpus.live.hub import registry
from corpus.live.setup import configure_hub


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the live hub (CORPUS_FEED) and the nightly scheduler
    (CORPUS_SCHEDULER=1). Both are opt-in; an unconfigured feature is a
    stated fact on /live/status, never a silent absence."""
    configure_hub()
    if registry.hub is not None:
        registry.hub.start()
    scheduler = None
    if os.environ.get("CORPUS_SCHEDULER") == "1":
        from corpus.jobs.scheduler import create_scheduler

        scheduler = create_scheduler()
        scheduler.start()
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        if registry.hub is not None:
            await registry.hub.stop()


def create_app() -> FastAPI:
    app = FastAPI(title="CORPUS", docs_url="/docs", redoc_url=None, lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(auth_kite.router)
    app.include_router(planner.router)
    app.include_router(allocation.router)
    app.include_router(sim.router)
    app.include_router(research.router)
    app.include_router(alerts.router)
    app.include_router(live.router)
    return app


app = create_app()
