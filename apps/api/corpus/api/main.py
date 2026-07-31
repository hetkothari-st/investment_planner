from fastapi import FastAPI

from corpus.api.routers import auth_kite, health


def create_app() -> FastAPI:
    app = FastAPI(title="CORPUS", docs_url="/docs", redoc_url=None)
    app.include_router(health.router)
    app.include_router(auth_kite.router)
    return app


app = create_app()
