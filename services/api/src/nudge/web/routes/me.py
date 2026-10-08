from fastapi import APIRouter

from nudge.web.deps import CurrentUserDep

router = APIRouter(prefix="/v1", tags=["me"])


@router.get("/me")
async def me(user: CurrentUserDep) -> dict[str, str | None]:
    """Smoke test for auth."""
    return {"id": user.id, "email": user.email}
