from fastapi import FastAPI

from corpus.api.routers import auth_kite, health, planner, sim


def create_app() -> FastAPI:
    app = FastAPI(title="CORPUS", docs_url="/docs", redoc_url=None)
    app.include_router(health.router)
    app.include_router(auth_kite.router)
    app.include_router(planner.router)
    app.include_router(sim.router)
    return app


app = create_app()
