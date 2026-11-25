"""Rotas dos produtos monitorados. Todas exigem login."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import CurrentUser, ProductServiceDep
from app.models.product import Price, PricePoint, Product, ProductUpdate

router = APIRouter(prefix="/products", tags=["produtos"])


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=2048)
    target_price: Price


@router.post("", status_code=status.HTTP_201_CREATED, summary="Cadastra e coleta o preço")
async def create_product(
    body: ProductCreate, user: CurrentUser, service: ProductServiceDep
) -> Product:
    return await service.create(user.id, body.url, body.target_price)


@router.get("", summary="Lista os produtos do usuário")
async def list_products(service: ProductServiceDep) -> list[Product]:
    return await service.list_all()


@router.get("/{product_id}", summary="Detalha um produto")
async def get_product(product_id: UUID, service: ProductServiceDep) -> Product:
    return await service.get(product_id)


@router.patch("/{product_id}", summary="Altera o preço-alvo ou pausa o monitoramento")
async def update_product(
    product_id: UUID, changes: ProductUpdate, service: ProductServiceDep
) -> Product:
    return await service.update(product_id, changes)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Exclui um produto")
async def delete_product(product_id: UUID, service: ProductServiceDep) -> None:
    await service.delete(product_id)


@router.get("/{product_id}/history", summary="Histórico de preços, do mais antigo ao mais novo")
async def get_history(
    product_id: UUID,
    service: ProductServiceDep,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> list[PricePoint]:
    return await service.history(product_id, days)
