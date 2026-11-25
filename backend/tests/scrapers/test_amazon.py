from decimal import Decimal

import pytest

from app.models.scrape import Availability, ScrapeResult, Store
from app.scrapers.amazon import AmazonScraper
from app.scrapers.exceptions import BlockedError, ParseError
from tests.scrapers.helpers import load_fixture, make_fetcher, serve

URL = "https://www.amazon.com.br/dp/B000000000"


async def test_reads_offer_fields() -> None:
    async with make_fetcher(serve(load_fixture("amazon_product.html"))) as fetcher:
        result = await AmazonScraper(fetcher).fetch_price(URL)
    assert result == ScrapeResult(
        store=Store.AMAZON_BR,
        title="Alto-falante Exemplo com Alexa",
        price=Decimal("1289.5"),
        image_url="https://m.media-amazon.com/large.jpg",
        availability=Availability.IN_STOCK,
    )


async def test_falls_back_to_displayed_price_ignoring_original() -> None:
    html = load_fixture("amazon_product.html").replace("customerVisiblePrice", "removed")
    async with make_fetcher(serve(html)) as fetcher:
        result = await AmazonScraper(fetcher).fetch_price(URL)
    assert result.price == Decimal("1289.50")


async def test_unavailable_product_has_no_price() -> None:
    async with make_fetcher(serve(load_fixture("amazon_unavailable.html"))) as fetcher:
        result = await AmazonScraper(fetcher).fetch_price(URL)
    assert result.price is None
    assert result.availability is Availability.OUT_OF_STOCK


async def test_detects_captcha() -> None:
    async with make_fetcher(serve(load_fixture("amazon_captcha.html"))) as fetcher:
        with pytest.raises(BlockedError):
            await AmazonScraper(fetcher).fetch_price(URL)


async def test_page_without_product_is_a_parse_error() -> None:
    async with make_fetcher(serve("<html></html>")) as fetcher:
        with pytest.raises(ParseError):
            await AmazonScraper(fetcher).fetch_price(URL)
