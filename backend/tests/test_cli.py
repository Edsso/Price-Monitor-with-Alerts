from decimal import Decimal

import pytest

from app import cli
from app.models.scrape import Availability, ScrapeResult, Store


@pytest.mark.parametrize(
    ("price", "currency", "expected"),
    [
        (Decimal("1234567.5"), "BRL", "R$ 1.234.567,50"),
        (Decimal("10"), "USD", "USD 10,00"),
        (None, "BRL", "indisponível"),
    ],
)
def test_format_price(price: Decimal | None, currency: str, expected: str) -> None:
    assert cli.format_price(price, currency) == expected


def test_prints_result(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    async def fake_scrape(url: str) -> ScrapeResult:
        return ScrapeResult(
            store=Store.AMAZON_BR,
            title="Fone",
            price=Decimal("99.9"),
            availability=Availability.IN_STOCK,
        )

    monkeypatch.setattr(cli, "scrape", fake_scrape)
    assert cli.main(["https://www.amazon.com.br/dp/B1"]) == 0
    output = capsys.readouterr().out
    assert "Fone" in output
    assert "R$ 99,90" in output


def test_unsupported_store_prints_clear_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["https://www.exemplo.com/produto"]) == 1
    assert "Loja não suportada" in capsys.readouterr().err
