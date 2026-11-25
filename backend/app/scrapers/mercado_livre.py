"""Scraper do Mercado Livre."""

from decimal import Decimal

import httpx
from bs4 import BeautifulSoup

from app.models.scrape import Store
from app.scrapers.base import BaseScraper
from app.scrapers.exceptions import BlockedError
from app.scrapers.parsing import (
    ProductData,
    extract_json_ld,
    extract_meta_tags,
    parse_brl_price,
    select_text,
)


class MercadoLivreScraper(BaseScraper):
    store = Store.MERCADO_LIVRE
    domains = ("mercadolivre.com.br",)

    def _extract(self, soup: BeautifulSoup) -> ProductData:
        # O CSS vem antes das meta tags só no título, pois `og:title` inclui o preço.
        title = ProductData(title=select_text(soup, "h1.ui-pdp-title"))
        price = ProductData(price=self._displayed_price(soup))
        return extract_json_ld(soup).merge(title).merge(extract_meta_tags(soup)).merge(price)

    def _raise_if_blocked(self, response: httpx.Response, soup: BeautifulSoup) -> None:
        if "account-verification" in response.url.path or "/login" in response.url.path:
            raise BlockedError("O Mercado Livre pediu verificação de acesso.")

    @staticmethod
    def _displayed_price(soup: BeautifulSoup) -> Decimal | None:
        # A segunda linha é o preço atual; a primeira é o preço original riscado.
        line = ".ui-pdp-price__second-line .andes-money-amount"
        whole = select_text(soup, f"{line}__fraction")
        cents = select_text(soup, f"{line}__cents")
        return parse_brl_price(f"{whole},{cents or '00'}") if whole else None
