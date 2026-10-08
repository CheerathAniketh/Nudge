from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    # Later: also report the time of the last successful monitoring cycle.
    return {"status": "ok"}
