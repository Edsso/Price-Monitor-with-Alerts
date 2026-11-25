"""Envio dos e-mails de alerta pelo Resend."""

import asyncio
from typing import Protocol

import resend
from jinja2 import Environment, PackageLoader, StrictUndefined
from resend.exceptions import ResendError

from app.core.config import JobSettings
from app.core.formatting import format_price
from app.models.product import Product

_MAX_SUBJECT_TITLE = 80
# O título vem da loja: autoescape impede que ele injete HTML no e-mail.
_templates = Environment(
    loader=PackageLoader("app"), autoescape=True, undefined=StrictUndefined, trim_blocks=True
)


class EmailError(Exception):
    """O e-mail não pôde ser enviado."""


class AlertSender(Protocol):
    async def send_alert(self, recipient: str, product: Product) -> None: ...


class ResendAlertSender:
    def __init__(self, settings: JobSettings) -> None:
        self._settings = settings
        resend.api_key = settings.resend_api_key.get_secret_value()

    async def send_alert(self, recipient: str, product: Product) -> None:
        """Envia o alerta de preço.

        Raises:
            EmailError: se o Resend recusar ou estiver inacessível.
        """
        params: resend.Emails.SendParams = {
            "from": self._settings.email_from,
            "to": [recipient],
            "subject": alert_subject(product),
            "html": render_alert(product, self._settings.frontend_url),
        }
        try:
            # O SDK é síncrono: a thread evita bloquear a API durante o envio.
            await asyncio.to_thread(resend.Emails.send, params)
        except (ResendError, RuntimeError) as error:
            raise EmailError("Não foi possível enviar o e-mail de alerta.") from error


def alert_subject(product: Product) -> str:
    title = " ".join(product.title.split())
    if len(title) > _MAX_SUBJECT_TITLE:
        title = title[: _MAX_SUBJECT_TITLE - 1].rstrip() + "…"
    return f"{format_price(product.current_price, product.currency)}: {title}"


def render_alert(product: Product, frontend_url: str) -> str:
    return _templates.get_template("price_alert.html").render(
        title=product.title,
        image_url=_https_only(product.image_url),
        current_price=format_price(product.current_price, product.currency),
        target_price=format_price(product.target_price, product.currency),
        product_url=product.url,
        details_url=f"{frontend_url.rstrip('/')}/products/{product.id}",
    )


def _https_only(url: str | None) -> str | None:
    return url if url and url.startswith("https://") else None
