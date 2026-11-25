"""Modelos das tabelas do banco."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.scrape import Store

# Mesmos limites de numeric(12, 2) no banco.
Price = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


class Product(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    user_id: UUID
    url: str
    store: Store
    title: str
    image_url: str | None
    target_price: Decimal
    current_price: Decimal | None
    currency: str
    is_active: bool
    last_checked_at: datetime | None
    last_error: str | None
    created_at: datetime


class NewProduct(BaseModel):
    """Produto pronto para inserção, já com os dados da primeira coleta."""

    user_id: UUID
    url: str
    store: Store
    title: str
    image_url: str | None
    target_price: Price
    current_price: Decimal | None
    currency: str
    last_checked_at: datetime


class ProductUpdate(BaseModel):
    """Campos que o usuário pode alterar; os omitidos ficam como estão."""

    model_config = ConfigDict(extra="forbid")

    target_price: Price | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _requires_a_change(self) -> Self:
        if self.target_price is None and self.is_active is None:
            raise ValueError("informe ao menos um campo para alterar")
        return self


class PricePoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    price: Decimal
    checked_at: datetime
