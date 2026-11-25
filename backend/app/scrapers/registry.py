"""Escolha do scraper a partir do domínio da URL."""

from app.scrapers.amazon import AmazonScraper
from app.scrapers.base import BaseScraper
from app.scrapers.exceptions import UnsupportedStoreError
from app.scrapers.http import PageFetcher
from app.scrapers.mercado_livre import MercadoLivreScraper

SCRAPERS: tuple[type[BaseScraper], ...] = (MercadoLivreScraper, AmazonScraper)


def get_scraper(url: str, fetcher: PageFetcher) -> BaseScraper:
    """Cria o scraper da loja à qual a URL pertence.

    Raises:
        InvalidUrlError: se a URL for inválida.
        UnsupportedStoreError: se nenhuma loja atender ao domínio.
    """
    for scraper in SCRAPERS:
        if scraper.supports(url):
            return scraper(fetcher)
    raise UnsupportedStoreError("Loja não suportada. Use Mercado Livre ou Amazon Brasil.")
