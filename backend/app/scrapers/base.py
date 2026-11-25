"""Contrato comum dos scrapers (padrão Strategy)."""

from abc import ABC, abstractmethod
from typing import ClassVar

import httpx
from bs4 import BeautifulSoup
from pydantic import ValidationError

from app.models.scrape import Availability, ScrapeResult, Store
from app.scrapers.exceptions import ParseError, UnsupportedStoreError
from app.scrapers.http import PageFetcher
from app.scrapers.parsing import ProductData
from app.scrapers.urls import host_matches, parse_url


class BaseScraper(ABC):
    """Baixa a página de um produto e extrai os dados; cada loja define como extrair."""

    store: ClassVar[Store]
    domains: ClassVar[tuple[str, ...]]

    def __init__(self, fetcher: PageFetcher) -> None:
        self._fetcher = fetcher

    @classmethod
    def supports(cls, url: str) -> bool:
        return host_matches(parse_url(url).host, cls.domains)

    async def fetch_price(self, url: str) -> ScrapeResult:
        """Coleta os dados atuais do produto.

        Raises:
            ScraperError: se a coleta falhar por qualquer motivo esperado.
        """
        if not self.supports(url):
            raise UnsupportedStoreError("A URL não pertence a esta loja.")
        response = await self._fetcher.fetch(url, self.domains)
        soup = BeautifulSoup(response.text, "html.parser")
        self._raise_if_blocked(response, soup)
        return self._build_result(self._extract(soup))

    @abstractmethod
    def _extract(self, soup: BeautifulSoup) -> ProductData:
        """Extrai os dados da página, deixando vazio o que não encontrar."""

    @abstractmethod
    def _raise_if_blocked(self, response: httpx.Response, soup: BeautifulSoup) -> None:
        """Lança `BlockedError` se a página for um captcha ou pedido de verificação."""

    def _build_result(self, data: ProductData) -> ScrapeResult:
        if data.title is None:
            raise ParseError("Não foi possível identificar o produto na página.")
        if data.price is None and data.availability is not Availability.OUT_OF_STOCK:
            raise ParseError("Não foi possível encontrar o preço na página.")
        try:
            return ScrapeResult(
                store=self.store,
                title=data.title,
                price=data.price,
                currency=data.currency or "BRL",
                image_url=data.image_url,
                availability=data.availability,
            )
        except ValidationError as error:
            raise ParseError("A página contém dados inválidos do produto.") from error
