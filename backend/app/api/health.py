from fastapi import APIRouter

router = APIRouter(tags=["sistema"])


@router.get("/health", summary="Informa que a API está no ar")
async def health() -> dict[str, str]:
    return {"status": "ok"}
