from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: str
    service: str


@router.get("/health", response_model=Health)
async def health() -> Health:
    return Health(status="ok", service="corpus-api")
