"""Scraper da Amazon Brasil."""

from decimal import Decimal

import httpx
from bs4 import BeautifulSoup

from app.models.scrape import Availability, Store
from app.scrapers.base import BaseScraper
from app.scrapers.exceptions import BlockedError
from app.scrapers.parsing import (
    ProductData,
    extract_json_ld,
    parse_brl_price,
    parse_machine_price,
    select_attr,
    select_text,
)

# Campos ocultos da oferta principal, mais estáveis que o preço exibido.
_PRICE_INPUTS = (
    'input[name$="[customerVisiblePrice][amount]"]',
    "input#twister-plus-price-data-price",
)
_CURRENCY_INPUT = 'input[name$="[customerVisiblePrice][currencyCode]"]'
# `.priceToPay` exclui o preço "De:", que aparece riscado.
_DISPLAYED_PRICES = (
    ".priceToPay .a-offscreen",
    '.priceToPay [aria-hidden="true"]',
    "#corePrice_feature_div .a-price:not(.a-text-price) .a-offscreen",
)


class AmazonScraper(BaseScraper):
    store = Store.AMAZON_BR
    domains = ("amazon.com.br",)

    def _extract(self, soup: BeautifulSoup) -> ProductData:
        # A Amazon costuma não publicar JSON-LD, mas ele tem prioridade se existir.
        return extract_json_ld(soup).merge(self._extract_page(soup))

    def _raise_if_blocked(self, response: httpx.Response, soup: BeautifulSoup) -> None:
        is_captcha = soup.select_one('form[action*="validateCaptcha"]') is not None
        if is_captcha or response.url.path.startswith("/ap/signin"):
            raise BlockedError("A Amazon pediu verificação de acesso.")

    def _extract_page(self, soup: BeautifulSoup) -> ProductData:
        availability = self._availability(soup)
        # Esgotado, a página ainda pode exibir preços de outras ofertas.
        price = None if availability is Availability.OUT_OF_STOCK else self._price(soup)
        if price is not None:
            availability = Availability.IN_STOCK
        return ProductData(
            title=select_text(soup, "#productTitle"),
            price=price,
            currency=select_attr(soup, _CURRENCY_INPUT, "value"),
            image_url=(
                select_attr(soup, "#landingImage", "data-old-hires")
                or select_attr(soup, "#landingImage", "src")
            ),
            availability=availability,
        )

    @staticmethod
    def _price(soup: BeautifulSoup) -> Decimal | None:
        for selector in _PRICE_INPUTS:
            if price := parse_machine_price(select_attr(soup, selector, "value")):
                return price
        for selector in _DISPLAYED_PRICES:
            text = (select_text(soup, selector) or "").replace(" ", "")
            if price := parse_brl_price(text):
                return price
        return None

    @staticmethod
    def _availability(soup: BeautifulSoup) -> Availability:
        text = (select_text(soup, "#availability") or "").lower()
        is_unavailable = "não disponível" in text or "indisponível" in text
        if is_unavailable or soup.select_one("#outOfStock"):
            return Availability.OUT_OF_STOCK
        return Availability.UNKNOWN
