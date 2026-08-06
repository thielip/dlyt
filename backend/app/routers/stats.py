from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import presence as presence_service

router = APIRouter(prefix="/api", tags=["stats"])


class PresenceBody(BaseModel):
    visitorId: str = Field(min_length=8, max_length=64)
    pageHit: bool = False


class StatsResponse(BaseModel):
    onlineNow: int
    pageViewsTotal: int


@router.get("/stats", response_model=StatsResponse)
def get_stats() -> StatsResponse:
    return StatsResponse(**presence_service.snapshot())


@router.post("/presence", response_model=StatsResponse)
def post_presence(body: PresenceBody) -> StatsResponse:
    try:
        data = presence_service.heartbeat(body.visitorId, page_hit=body.pageHit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StatsResponse(**data)
