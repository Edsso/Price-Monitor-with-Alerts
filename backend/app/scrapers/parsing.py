"""Funções puras de extração, compartilhadas entre as lojas."""

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from bs4 import BeautifulSoup

from app.models.scrape import Availability

_BRL_NUMBER = re.compile(r"\d[\d.]*(?:,\d{1,2})?")


@dataclass(frozen=True)
class ProductData:
    """Dados parciais de um produto; cada fonte preenche o que conseguir."""

    title: str | None = None
    price: Decimal | None = None
    currency: str | None = None
    image_url: str | None = None
    availability: Availability = Availability.UNKNOWN

    def merge(self, fallback: "ProductData") -> "ProductData":
        """Completa os campos ausentes com os de `fallback`.

        Preço e moeda vêm sempre da mesma fonte, para nunca combinar valores incompatíveis.
        """
        price_source = self if self.price is not None else fallback
        return ProductData(
            title=self.title or fallback.title,
            price=price_source.price,
            currency=price_source.currency,
            image_url=self.image_url or fallback.image_url,
            availability=(
                self.availability
                if self.availability is not Availability.UNKNOWN
                else fallback.availability
            ),
        )


def parse_machine_price(value: object) -> Decimal | None:
    """Converte preços de dados estruturados, com ponto decimal (ex.: `1234.56`)."""
    if isinstance(value, bool) or not isinstance(value, str | int | float | Decimal):
        return None
    if isinstance(value, str) and "," in value:
        return parse_brl_price(value)
    try:
        price = Decimal(str(value).strip())
    except InvalidOperation:
        return None
    return price if price.is_finite() and price > 0 else None


def parse_brl_price(text: str | None) -> Decimal | None:
    """Converte preços exibidos no formato brasileiro (ex.: `R$ 1.234,56`)."""
    match = _BRL_NUMBER.search(text or "")
    if match is None:
        return None
    try:
        price = Decimal(match.group().replace(".", "").replace(",", "."))
    except InvalidOperation:
        return None
    return price if price > 0 else None


def parse_availability(value: object) -> Availability:
    """Interpreta valores do schema.org (ex.: `https://schema.org/InStock`)."""
    name = value.rstrip("/").rsplit("/", 1)[-1].lower() if isinstance(value, str) else ""
    if name in {"instock", "limitedavailability", "onlineonly", "instoreonly"}:
        return Availability.IN_STOCK
    if name in {"outofstock", "soldout", "discontinued"}:
        return Availability.OUT_OF_STOCK
    return Availability.UNKNOWN


def select_text(soup: BeautifulSoup, selector: str) -> str | None:
    element = soup.select_one(selector)
    return (" ".join(element.get_text(" ").split()) or None) if element else None


def select_attr(soup: BeautifulSoup, selector: str, attr: str) -> str | None:
    element = soup.select_one(selector)
    value = element.get(attr) if element else None
    return (value.strip() or None) if isinstance(value, str) else None


def extract_json_ld(soup: BeautifulSoup) -> ProductData:
    """Extrai o primeiro `schema.org/Product` com preço ou, na falta, o primeiro da página."""
    products = [
        _product_from_node(node)
        for script in soup.select('script[type="application/ld+json"]')
        for node in _iter_nodes(_load_json(script.get_text()))
        if _has_type(node, "Product")
    ]
    with_price = next((product for product in products if product.price is not None), None)
    return with_price or (products[0] if products else ProductData())


def extract_meta_tags(soup: BeautifulSoup) -> ProductData:
    """Extrai dados de Open Graph e microdata."""

    def meta(*names: str) -> str | None:
        for name in names:
            for attr in ("property", "name", "itemprop"):
                if value := select_attr(soup, f'meta[{attr}="{name}"]', "content"):
                    return value
        return None

    return ProductData(
        title=meta("og:title"),
        price=parse_machine_price(
            meta("og:price:amount", "product:price:amount", "og:price", "price")
        ),
        currency=meta("og:price:currency", "product:price:currency", "priceCurrency"),
        image_url=meta("og:image"),
        availability=parse_availability(meta("og:availability", "product:availability")),
    )


def _load_json(text: str) -> Any:
    try:
        # Decimal evita o arredondamento de ponto flutuante em preços.
        return json.loads(text, parse_float=Decimal, strict=False)
    except (ValueError, InvalidOperation, RecursionError):
        return None


def _iter_nodes(data: Any) -> Iterator[dict[str, Any]]:
    # Percorre só os níveis principais: descer em tudo encontraria produtos recomendados.
    if isinstance(data, list):
        for item in data:
            yield from _iter_nodes(item)
    elif isinstance(data, dict):
        yield data
        for key in ("@graph", "mainEntity"):
            yield from _iter_nodes(data.get(key))


def _has_type(node: dict[str, Any], name: str) -> bool:
    types = node.get("@type")
    return name in types if isinstance(types, list) else types == name


def _product_from_node(node: dict[str, Any]) -> ProductData:
    price, currency, availability = _best_offer(node.get("offers"))
    title = node.get("name")
    return ProductData(
        title=(title.strip() or None) if isinstance(title, str) else None,
        price=price,
        currency=currency,
        image_url=_first_image(node.get("image")),
        availability=availability,
    )


def _best_offer(data: Any) -> tuple[Decimal | None, str | None, Availability]:
    """Escolhe a primeira oferta em estoque ou, na falta, a primeira com preço."""
    offers = []
    for offer in data if isinstance(data, list) else [data]:
        if not isinstance(offer, dict):
            continue
        currency = offer.get("priceCurrency")
        offers.append(
            (
                parse_machine_price(offer.get("price") or offer.get("lowPrice")),
                currency if isinstance(currency, str) else None,
                parse_availability(offer.get("availability")),
            )
        )
    priced = [offer for offer in offers if offer[0] is not None]
    in_stock = [offer for offer in priced if offer[2] is Availability.IN_STOCK]
    candidates = in_stock or priced or offers
    return candidates[0] if candidates else (None, None, Availability.UNKNOWN)


def _first_image(image: Any) -> str | None:
    if isinstance(image, list):
        image = image[0] if image else None
    if isinstance(image, dict):
        image = image.get("url") or image.get("contentUrl")
    return image if isinstance(image, str) and image else None
