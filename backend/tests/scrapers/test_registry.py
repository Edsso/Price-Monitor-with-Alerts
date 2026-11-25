import pytest

from app.scrapers.amazon import AmazonScraper
from app.scrapers.base import BaseScraper
from app.scrapers.exceptions import InvalidUrlError, UnsupportedStoreError
from app.scrapers.mercado_livre import MercadoLivreScraper
from app.scrapers.registry import get_scraper
from tests.scrapers.helpers import make_fetcher, serve


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.mercadolivre.com.br/x/p/MLB1", MercadoLivreScraper),
        ("https://produto.mercadolivre.com.br/MLB-1", MercadoLivreScraper),
        ("https://www.amazon.com.br/dp/B1", AmazonScraper),
        ("https://amazon.com.br/dp/B1", AmazonScraper),
    ],
)
async def test_chooses_scraper_by_domain(url: str, expected: type[BaseScraper]) -> None:
    async with make_fetcher(serve("")) as fetcher:
        assert isinstance(get_scraper(url, fetcher), expected)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.amazon.com/dp/B1",
        "https://amazon.com.br.evil.com/dp/B1",
        "https://notamazon.com.br/dp/B1",
    ],
)
async def test_unsupported_store(url: str) -> None:
    async with make_fetcher(serve("")) as fetcher:
        with pytest.raises(UnsupportedStoreError, match="não suportada"):
            get_scraper(url, fetcher)


async def test_invalid_url() -> None:
    async with make_fetcher(serve("")) as fetcher:
        with pytest.raises(InvalidUrlError):
            get_scraper("não é url", fetcher)
