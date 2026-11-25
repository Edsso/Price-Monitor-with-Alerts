from decimal import Decimal

import httpx
import pytest

from app.models.scrape import Availability, ScrapeResult, Store
from app.scrapers.exceptions import BlockedError, ParseError, UnsupportedStoreError
from app.scrapers.mercado_livre import MercadoLivreScraper
from tests.scrapers.helpers import load_fixture, make_fetcher, serve

URL = "https://produto.mercadolivre.com.br/MLB-123-fone-_JM"


async def test_reads_json_ld() -> None:
    async with make_fetcher(serve(load_fixture("mercado_livre_json_ld.html"))) as fetcher:
        result = await MercadoLivreScraper(fetcher).fetch_price(URL)
    assert result == ScrapeResult(
        store=Store.MERCADO_LIVRE,
        title="Fone Bluetooth Exemplo",
        price=Decimal("1299.90"),
        image_url="https://http2.mlstatic.com/produto.jpg",
        availability=Availability.IN_STOCK,
    )


async def test_falls_back_to_html_ignoring_original_price() -> None:
    async with make_fetcher(serve(load_fixture("mercado_livre_html.html"))) as fetcher:
        result = await MercadoLivreScraper(fetcher).fetch_price(URL)
    assert result.title == "Fone Bluetooth Exemplo"
    assert result.price == Decimal("1299.90")
    assert result.image_url == "https://http2.mlstatic.com/og.jpg"


async def test_detects_account_verification() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/gz/account-verification":
            return httpx.Response(200, html="<html></html>")
        location = "https://www.mercadolivre.com.br/gz/account-verification?go=x"
        return httpx.Response(302, headers={"Location": location})

    async with make_fetcher(handler) as fetcher:
        with pytest.raises(BlockedError):
            await MercadoLivreScraper(fetcher).fetch_price(URL)


@pytest.mark.parametrize("html", ["<html></html>", '<h1 class="ui-pdp-title">Sem preço</h1>'])
async def test_incomplete_page_is_a_parse_error(html: str) -> None:
    async with make_fetcher(serve(html)) as fetcher:
        with pytest.raises(ParseError):
            await MercadoLivreScraper(fetcher).fetch_price(URL)


async def test_invalid_currency_is_a_parse_error() -> None:
    html = load_fixture("mercado_livre_json_ld.html").replace('"BRL"', '"R$"')
    async with make_fetcher(serve(html)) as fetcher:
        with pytest.raises(ParseError):
            await MercadoLivreScraper(fetcher).fetch_price(URL)


async def test_refuses_url_from_other_store() -> None:
    async with make_fetcher(serve("")) as fetcher:
        with pytest.raises(UnsupportedStoreError):
            await MercadoLivreScraper(fetcher).fetch_price("https://www.amazon.com.br/dp/X")
