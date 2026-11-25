"""Formatação de valores para exibição em português."""

from decimal import Decimal


def format_price(price: Decimal | None, currency: str) -> str:
    if price is None:
        return "indisponível"
    number = f"{price:,.2f}".translate(str.maketrans(",.", ".,"))
    return f"{'R$' if currency == 'BRL' else currency} {number}"
