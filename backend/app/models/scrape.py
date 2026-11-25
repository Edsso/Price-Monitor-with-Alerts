"""Modelos do resultado da coleta de preço."""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Store(StrEnum):
    MERCADO_LIVRE = "mercado_livre"
    AMAZON_BR = "amazon_br"


class Availability(StrEnum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    UNKNOWN = "unknown"


class ScrapeResult(BaseModel):
    """Dados extraídos da página. `price` só pode faltar se o produto estiver esgotado."""

    model_config = ConfigDict(frozen=True)

    store: Store
    title: str = Field(min_length=1)
    price: Annotated[Decimal, Field(gt=0)] | None
    currency: str = Field(default="BRL", pattern=r"^[A-Z]{3}$")
    image_url: str | None = None
    availability: Availability = Availability.UNKNOWN

    @model_validator(mode="after")
    def _price_required_unless_out_of_stock(self) -> Self:
        if self.price is None and self.availability is not Availability.OUT_OF_STOCK:
            raise ValueError("price é obrigatório para produtos não esgotados")
        return self
