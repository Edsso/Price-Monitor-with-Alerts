"""Operações sobre produtos, feitas em nome do usuário ou pelo job."""

from datetime import datetime
from typing import Any
from uuid import UUID

from postgrest import AsyncPostgrestClient

from app.models.product import NewProduct, PricePoint, Product, ProductUpdate
from app.models.scrape import ScrapeResult
from app.repositories.client import execute, fetch_all


class ProductRepository:
    """O acesso depende do cliente recebido: com o do usuário, o RLS limita os resultados."""

    def __init__(self, client: AsyncPostgrestClient) -> None:
        self._client = client

    async def create(self, product: NewProduct) -> Product:
        """Cadastra o produto; o banco registra o primeiro preço no histórico.

        Raises:
            DuplicateProductError: se o usuário já tiver cadastrado a URL.
        """
        rows = await execute(self._client.table("products").insert(product.model_dump(mode="json")))
        return Product.model_validate(rows[0])

    async def list_all(self) -> list[Product]:
        rows = await fetch_all(
            lambda: (
                self._client.table("products")
                .select("*")
                .order("created_at", desc=True)
                .order("id")
            )
        )
        return [Product.model_validate(row) for row in rows]

    async def list_active(self) -> list[Product]:
        rows = await fetch_all(
            lambda: self._client.table("products").select("*").eq("is_active", "true").order("id")
        )
        return [Product.model_validate(row) for row in rows]

    async def get(self, product_id: UUID) -> Product | None:
        rows = await execute(self._client.table("products").select("*").eq("id", str(product_id)))
        return Product.model_validate(rows[0]) if rows else None

    async def update(self, product_id: UUID, changes: ProductUpdate) -> Product | None:
        values = changes.model_dump(mode="json", exclude_none=True)
        query = self._client.table("products").update(values).eq("id", str(product_id))
        rows = await execute(query)
        return Product.model_validate(rows[0]) if rows else None

    async def delete(self, product_id: UUID) -> bool:
        """Exclui o produto e informa se ele existia."""
        query = self._client.table("products").delete().eq("id", str(product_id))
        return bool(await execute(query))

    async def list_history(self, product_id: UUID, since: datetime) -> list[PricePoint]:
        rows = await fetch_all(
            lambda: (
                self._client.table("price_history")
                .select("price,checked_at")
                .eq("product_id", str(product_id))
                .gte("checked_at", since.isoformat())
                .order("checked_at")
                .order("id")
            )
        )
        return [PricePoint.model_validate(row) for row in rows]

    async def record_check(self, product_id: UUID, result: ScrapeResult) -> None:
        """Salva uma coleta bem-sucedida, com o histórico (somente job)."""
        params: Any = {
            "p_product_id": str(product_id),
            "p_title": result.title,
            "p_image_url": result.image_url,
            "p_price": None if result.price is None else str(result.price),
            "p_currency": result.currency,
        }
        await execute(self._client.rpc("record_price_check", params))

    async def record_error(self, product_id: UUID, message: str, checked_at: datetime) -> None:
        """Registra a falha de uma coleta, mantendo o último preço (somente job)."""
        values = {"last_error": message, "last_checked_at": checked_at.isoformat()}
        await execute(self._client.table("products").update(values).eq("id", str(product_id)))
