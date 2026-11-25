from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
import resend
from resend.exceptions import ResendError

from app.models.product import Product
from app.models.scrape import Store
from app.services.alert_rule import reached_target
from app.services.email import EmailError, ResendAlertSender, alert_subject, render_alert
from tests.tokens import JOB, USER_ID


def make_product(**overrides: Any) -> Product:
    values: dict[str, Any] = {
        "id": UUID(int=1),
        "user_id": UUID(USER_ID),
        "url": "https://www.amazon.com.br/dp/1?a=1&b=2",
        "store": Store.AMAZON_BR,
        "title": "Fone",
        "image_url": "https://img/1.jpg",
        "target_price": Decimal("1500.00"),
        "current_price": Decimal("1289.50"),
        "currency": "BRL",
        "is_active": True,
        "last_checked_at": None,
        "last_error": None,
        "created_at": datetime(2026, 11, 25, tzinfo=UTC),
    }
    return Product(**{**values, **overrides})


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"current_price": Decimal("1499.99")}, True),
        ({"current_price": Decimal("1500.00")}, True),
        ({"current_price": Decimal("1500.01")}, False),
        ({"current_price": None}, False),
        ({"is_active": False}, False),
    ],
)
def test_alert_rule(overrides: dict[str, Any], expected: bool) -> None:
    assert reached_target(make_product(**overrides)) is expected


def test_template_shows_prices_and_links() -> None:
    html = render_alert(make_product(), "https://app.exemplo.com/")
    assert "R$ 1.289,50" in html
    assert "R$ 1.500,00" in html
    assert 'href="https://www.amazon.com.br/dp/1?a=1&amp;b=2"' in html
    assert f"https://app.exemplo.com/products/{UUID(int=1)}" in html
    assert "https://img/1.jpg" in html


def test_template_escapes_store_content() -> None:
    html = render_alert(make_product(title="<script>x</script>"), "https://app")
    assert "<script>" not in html


@pytest.mark.parametrize("image_url", [None, "javascript:alert(1)", "http://img/1.jpg"])
def test_template_omits_unsafe_image(image_url: str | None) -> None:
    assert "<img" not in render_alert(make_product(image_url=image_url), "https://app")


def test_subject_is_single_line_and_short() -> None:
    subject = alert_subject(make_product(title="Fone\r\nBcc: x " + "a" * 200))
    assert subject.startswith("R$ 1.289,50: Fone Bcc")
    assert "\n" not in subject
    assert len(subject) < 110


async def test_sends_with_resend(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[Any] = []
    monkeypatch.setattr(resend.Emails, "send", sent.append)
    await ResendAlertSender(JOB).send_alert("ana@exemplo.com", make_product())
    assert sent[0]["to"] == ["ana@exemplo.com"]
    assert sent[0]["from"] == JOB.email_from
    assert "R$ 1.289,50" in sent[0]["html"]


@pytest.mark.parametrize(
    "error",
    [RuntimeError("rede"), ResendError("500", "application_error", "falha", "tente depois")],
)
async def test_translates_send_failure(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    def fail(params: object) -> None:
        raise error

    monkeypatch.setattr(resend.Emails, "send", fail)
    with pytest.raises(EmailError):
        await ResendAlertSender(JOB).send_alert("ana@exemplo.com", make_product())
