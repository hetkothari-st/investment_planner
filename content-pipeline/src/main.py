from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="content-pipeline")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
