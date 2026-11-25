"""Job que verifica os preços de todos os produtos ativos."""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.models.product import Product
from app.repositories.alerts import AlertRepository
from app.repositories.exceptions import RepositoryError
from app.repositories.products import ProductRepository
from app.repositories.users import UserRepository
from app.scrapers.exceptions import ScraperError
from app.scrapers.http import PageFetcher
from app.scrapers.registry import get_scraper
from app.services.alert_rule import reached_target
from app.services.email import AlertSender, EmailError

logger = logging.getLogger(__name__)

_UNEXPECTED_ERROR = "Erro inesperado ao verificar o preço."


def _utc_now() -> datetime:
    return datetime.now(UTC)


class PriceCheckJob:
    def __init__(
        self,
        *,
        products: ProductRepository,
        alerts: AlertRepository,
        users: UserRepository,
        fetcher: PageFetcher,
        sender: AlertSender,
        alert_interval: timedelta,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._products = products
        self._alerts = alerts
        self._users = users
        self._fetcher = fetcher
        self._sender = sender
        self._alert_interval = alert_interval
        self._now = now
        self._lock = asyncio.Lock()

    async def run(self) -> None:
        """Verifica todos os produtos. Se já houver uma execução em andamento, não faz nada."""
        if self._lock.locked():
            logger.warning("Verificação ignorada: a anterior ainda está em andamento")
            return
        async with self._lock:
            try:
                active = await self._products.list_active()
            except RepositoryError:
                logger.exception("Não foi possível listar os produtos")
                return
            by_store: defaultdict[str, list[Product]] = defaultdict(list)
            for product in active:
                by_store[product.store].append(product)
            # Lojas em paralelo; produtos da mesma loja em sequência, para não sobrecarregá-la.
            await asyncio.gather(*(self._check_all(group) for group in by_store.values()))
            logger.info("Verificação concluída: %d produtos", len(active))

    async def _check_all(self, products: list[Product]) -> None:
        for product in products:
            await self._check_safely(product)

    async def _check_safely(self, product: Product) -> None:
        """Verifica um produto sem deixar que a falha dele afete os demais."""
        try:
            await self._check(product)
        except (ScraperError, EmailError) as error:
            logger.warning("Falha no produto %s: %s", product.id, error)
            await self._record_error(product, str(error))
        except Exception:
            logger.exception("Erro inesperado no produto %s", product.id)
            await self._record_error(product, _UNEXPECTED_ERROR)

    async def _check(self, product: Product) -> None:
        result = await get_scraper(product.url, self._fetcher).fetch_price(product.url)
        await self._products.record_check(product.id, result)
        # Relê o produto: o usuário pode ter mudado o alvo ou pausado durante o job.
        current = await self._products.get(product.id)
        if current is not None and reached_target(current):
            await self._alert(current)

    async def _alert(self, product: Product) -> None:
        since = self._now() - self._alert_interval
        if product.current_price is None or await self._alerts.exists_since(product.id, since):
            return
        recipient = await self._users.get_email(product.user_id)
        await self._sender.send_alert(recipient, product)
        await self._alerts.create(product.id, product.current_price)

    async def _record_error(self, product: Product, message: str) -> None:
        try:
            await self._products.record_error(product.id, message, self._now())
        except Exception:
            logger.exception("Não foi possível registrar o erro do produto %s", product.id)
