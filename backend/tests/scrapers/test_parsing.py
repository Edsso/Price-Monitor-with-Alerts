from decimal import Decimal

import pytest
from bs4 import BeautifulSoup
from pydantic import ValidationError

from app.models.scrape import Availability, ScrapeResult, Store
from app.scrapers.parsing import (
    ProductData,
    extract_json_ld,
    extract_meta_tags,
    parse_availability,
    parse_brl_price,
    parse_machine_price,
)


def make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def json_ld(content: str) -> BeautifulSoup:
    return make_soup(f'<script type="application/ld+json">{content}</script>')


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("R$ 1.234,56", Decimal("1234.56")),
        ("R$\xa0289,00", Decimal("289.00")),
        ("1.234", Decimal("1234")),
        ("1.234.567,8", Decimal("1234567.8")),
        ("R$ 0,00", None),
        ("indisponível", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_brl_price(text: str | None, expected: Decimal | None) -> None:
    assert parse_brl_price(text) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1234.56", Decimal("1234.56")),
        ("1.234", Decimal("1.234")),
        ("1.234,56", Decimal("1234.56")),
        (99, Decimal("99")),
        (19.9, Decimal("19.9")),
        ("NaN", None),
        ("Infinity", None),
        (-1, None),
        (True, None),
        (None, None),
        ("abc", None),
    ],
)
def test_parse_machine_price(value: object, expected: Decimal | None) -> None:
    assert parse_machine_price(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://schema.org/InStock", Availability.IN_STOCK),
        ("http://schema.org/OutOfStock", Availability.OUT_OF_STOCK),
        ("InStock", Availability.IN_STOCK),
        (None, Availability.UNKNOWN),
        ("???", Availability.UNKNOWN),
    ],
)
def test_parse_availability(value: object, expected: Availability) -> None:
    assert parse_availability(value) is expected


def test_json_ld_inside_graph_with_multiple_types() -> None:
    data = extract_json_ld(
        json_ld(
            '{"@graph": [{"@type": "WebPage"}, {"@type": ["Thing", "Product"], "name": "Fone",'
            '"image": [{"url": "https://img/1.jpg"}],'
            '"offers": {"price": 199.90, "priceCurrency": "BRL"}}]}'
        )
    )
    assert data == ProductData("Fone", Decimal("199.90"), "BRL", "https://img/1.jpg")


def test_json_ld_prefers_offer_in_stock() -> None:
    data = extract_json_ld(
        json_ld(
            '{"@type": "Product", "name": "X", "offers": ['
            '{"price": 10, "availability": "https://schema.org/OutOfStock"},'
            '{"price": 20, "availability": "https://schema.org/InStock"}]}'
        )
    )
    assert data.price == Decimal("20")
    assert data.availability is Availability.IN_STOCK


def test_json_ld_aggregate_offer_uses_low_price() -> None:
    data = extract_json_ld(json_ld('{"@type": "Product", "offers": {"lowPrice": "50.5"}}'))
    assert data.price == Decimal("50.5")


def test_json_ld_ignores_recommended_products() -> None:
    data = extract_json_ld(
        json_ld('{"@type": "ItemList", "itemListElement": [{"@type": "Product", "name": "X"}]}')
    )
    assert data == ProductData()


@pytest.mark.parametrize("content", ["{inválido", "null", "[]", '{"@type": "Product"}'])
def test_json_ld_tolerates_invalid_content(content: str) -> None:
    assert extract_json_ld(json_ld(content)) == ProductData()


def test_meta_tags() -> None:
    data = extract_meta_tags(
        make_soup(
            '<meta property="og:title" content="Fone">'
            '<meta property="og:price:amount" content="199.90">'
            '<meta property="og:price:currency" content="BRL">'
            '<meta property="og:image" content="https://img/1.jpg">'
        )
    )
    assert data == ProductData("Fone", Decimal("199.90"), "BRL", "https://img/1.jpg")


def test_merge_keeps_price_and_currency_from_same_source() -> None:
    merged = ProductData(title="A", currency="USD").merge(
        ProductData(title="B", price=Decimal("10"), currency="BRL")
    )
    assert merged == ProductData("A", Decimal("10"), "BRL")


def test_result_requires_price_unless_out_of_stock() -> None:
    with pytest.raises(ValidationError):
        ScrapeResult(store=Store.AMAZON_BR, title="X", price=None)
    result = ScrapeResult(
        store=Store.AMAZON_BR, title="X", price=None, availability=Availability.OUT_OF_STOCK
    )
    assert result.price is None
