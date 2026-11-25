"""Rotas chamadas pelo Supabase Cron."""

import hmac
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status

from app.api.dependencies import ResourcesDep

router = APIRouter(prefix="/jobs", tags=["jobs"])


def require_cron_secret(
    resources: ResourcesDep, x_cron_secret: Annotated[str | None, Header()] = None
) -> None:
    expected = resources.cron_secret.get_secret_value()
    # Comparação em tempo constante; em bytes porque o header pode ter caracteres não ASCII.
    if not hmac.compare_digest((x_cron_secret or "").encode(), expected.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Segredo inválido.")


@router.post(
    "/check-prices",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_cron_secret)],
    summary="Inicia a verificação de preços em segundo plano",
)
async def check_prices(resources: ResourcesDep, background: BackgroundTasks) -> dict[str, str]:
    background.add_task(resources.job.run)
    return {"status": "accepted"}
