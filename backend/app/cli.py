"""CLI: recebe a URL de um produto e imprime o preço atual.

Uso: python -m app.cli <url>
"""

import argparse
import asyncio
import sys
from collections.abc import Sequence
from decimal import Decimal

from app.core.config import get_settings
from app.models.scrape import Availability, ScrapeResult
from app.scrapers.exceptions import ScraperError
from app.scrapers.http import PageFetcher
from app.scrapers.registry import get_scraper

_AVAILABILITY_LABELS = {
    Availability.IN_STOCK: "em estoque",
    Availability.OUT_OF_STOCK: "esgotado",
    Availability.UNKNOWN: "não informada",
}


def format_price(price: Decimal | None, currency: str) -> str:
    if price is None:
        return "indisponível"
    number = f"{price:,.2f}".translate(str.maketrans(",.", ".,"))
    return f"{'R$' if currency == 'BRL' else currency} {number}"


def format_result(result: ScrapeResult) -> str:
    return "\n".join(
        (
            f"Produto:         {result.title}",
            f"Loja:            {result.store}",
            f"Preço:           {format_price(result.price, result.currency)}",
            f"Disponibilidade: {_AVAILABILITY_LABELS[result.availability]}",
            f"Imagem:          {result.image_url or '-'}",
        )
    )


async def scrape(url: str) -> ScrapeResult:
    async with PageFetcher(get_settings()) as fetcher:
        return await get_scraper(url, fetcher).fetch_price(url)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Consulta o preço atual de um produto.")
    parser.add_argument("url", help="link do produto no Mercado Livre ou na Amazon Brasil")
    args = parser.parse_args(argv)
    try:
        result = asyncio.run(scrape(args.url))
    except ScraperError as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    print(format_result(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
