"""Registro dos alertas enviados (somente job)."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from postgrest import AsyncPostgrestClient

from app.repositories.client import execute


class AlertRepository:
    def __init__(self, client: AsyncPostgrestClient) -> None:
        self._client = client

    async def exists_since(self, product_id: UUID, since: datetime) -> bool:
        query = (
            self._client.table("alerts")
            .select("id")
            .eq("product_id", str(product_id))
            .gte("sent_at", since.isoformat())
            .limit(1)
        )
        return bool(await execute(query))

    async def create(self, product_id: UUID, price: Decimal) -> None:
        values = {"product_id": str(product_id), "price": str(price)}
        await execute(self._client.table("alerts").insert(values))
