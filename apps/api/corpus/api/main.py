from fastapi import FastAPI

from corpus.api.routers import allocation, auth_kite, health, planner, research, sim


def create_app() -> FastAPI:
    app = FastAPI(title="CORPUS", docs_url="/docs", redoc_url=None)
    app.include_router(health.router)
    app.include_router(auth_kite.router)
    app.include_router(planner.router)
    app.include_router(allocation.router)
    app.include_router(sim.router)
    app.include_router(research.router)
    return app


app = create_app()
