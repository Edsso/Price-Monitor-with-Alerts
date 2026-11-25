"""Regra que decide quando um alerta deve ser enviado."""

from app.models.product import Product


def reached_target(product: Product) -> bool:
    """Indica se o produto, ativo e disponível, está no preço-alvo ou abaixo dele."""
    return (
        product.is_active
        and product.current_price is not None
        and product.current_price <= product.target_price
    )
