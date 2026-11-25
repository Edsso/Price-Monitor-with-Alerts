"""Regras de negócio dos produtos monitorados."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from app.models.product import NewProduct, PricePoint, Product, ProductUpdate
from app.repositories.products import ProductRepository
from app.scrapers.http import PageFetcher
from app.scrapers.registry import get_scraper
from app.scrapers.urls import parse_url


class ProductNotRegisteredError(Exception):
    """O produto não existe ou pertence a outro usuário."""


class ProductService:
    def __init__(self, repository: ProductRepository, fetcher: PageFetcher) -> None:
        self._repository = repository
        self._fetcher = fetcher

    async def create(self, user_id: UUID, url: str, target_price: Decimal) -> Product:
        """Faz a primeira coleta e cadastra o produto.

        Raises:
            ScraperError: se a coleta falhar.
            DuplicateProductError: se o usuário já monitorar a URL.
        """
        url = normalize_url(url)
        result = await get_scraper(url, self._fetcher).fetch_price(url)
        return await self._repository.create(
            NewProduct(
                user_id=user_id,
                url=url,
                store=result.store,
                title=result.title,
                image_url=result.image_url,
                target_price=target_price,
                current_price=result.price,
                currency=result.currency,
                last_checked_at=datetime.now(UTC),
            )
        )

    async def list_all(self) -> list[Product]:
        return await self._repository.list_all()

    async def get(self, product_id: UUID) -> Product:
        return _require(await self._repository.get(product_id))

    async def update(self, product_id: UUID, changes: ProductUpdate) -> Product:
        return _require(await self._repository.update(product_id, changes))

    async def delete(self, product_id: UUID) -> None:
        if not await self._repository.delete(product_id):
            raise ProductNotRegisteredError

    async def history(self, product_id: UUID, days: int) -> list[PricePoint]:
        await self.get(product_id)
        since = datetime.now(UTC) - timedelta(days=days)
        return await self._repository.list_history(product_id, since)


def normalize_url(url: str) -> str:
    """Padroniza a URL para que o mesmo link não seja cadastrado duas vezes."""
    parsed = parse_url(url)
    return str(parsed.copy_with(scheme="https", fragment=None))


def _require(product: Product | None) -> Product:
    if product is None:
        raise ProductNotRegisteredError
    return product
