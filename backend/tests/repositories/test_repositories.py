"""Testa as requisições enviadas ao PostgREST, sem acessar a internet."""

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import SupabaseSettings
from app.models.product import NewProduct, ProductUpdate
from app.models.scrape import Availability, ScrapeResult, Store
from app.repositories.alerts import AlertRepository
from app.repositories.client import PAGE_SIZE, service_client, user_client
from app.repositories.exceptions import DuplicateProductError, RepositoryError
from app.repositories.products import ProductRepository

PRODUCT_ID = UUID("00000000-0000-0000-0000-000000000001")
USER_ID = UUID("00000000-0000-0000-0000-00000000000a")
NOW = datetime(2026, 11, 25, 12, tzinfo=UTC)
SETTINGS = SupabaseSettings(
    url="https://projeto.supabase.co",
    publishable_key="publica",
    secret_key=SecretStr("secreta"),
)
ROW: dict[str, Any] = {
    "id": str(PRODUCT_ID),
    "user_id": str(USER_ID),
    "url": "https://www.amazon.com.br/dp/1",
    "store": "amazon_br",
    "title": "Fone",
    "image_url": None,
    "target_price": 90.1,
    "current_price": 100.55,
    "currency": "BRL",
    "is_active": True,
    "last_checked_at": NOW.isoformat(),
    "last_error": None,
    "created_at": NOW.isoformat(),
}


class FakePostgrest:
    """Responde na ordem definida e guarda as requisições recebidas."""

    def __init__(self) -> None:
        self.responses: list[httpx.Response] = []
        self.requests: list[httpx.Request] = []

    def reply(self, data: object, status: int = 200) -> None:
        self.responses.append(httpx.Response(status, json=data))

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responses.pop(0)

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]

    def last_body(self) -> Any:
        return json.loads(self.last.content)


@pytest.fixture
def server() -> FakePostgrest:
    return FakePostgrest()


@pytest.fixture
async def http(server: FakePostgrest) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(transport=httpx.MockTransport(server.handle)) as client:
        yield client


@pytest.fixture
def products(http: httpx.AsyncClient) -> ProductRepository:
    return ProductRepository(user_client(SETTINGS, http, "jwt"))


@pytest.fixture
def alerts(http: httpx.AsyncClient) -> AlertRepository:
    return AlertRepository(service_client(SETTINGS, http))


def new_product() -> NewProduct:
    return NewProduct(
        user_id=USER_ID,
        url=ROW["url"],
        store=Store.AMAZON_BR,
        title="Fone",
        image_url=None,
        target_price=Decimal("90.10"),
        current_price=Decimal("100.55"),
        currency="BRL",
        last_checked_at=NOW,
    )


async def test_user_client_uses_publishable_key_and_user_token(
    server: FakePostgrest, products: ProductRepository
) -> None:
    server.reply([])
    await products.list_all()
    assert server.last.headers["apikey"] == "publica"
    assert server.last.headers["Authorization"] == "Bearer jwt"
    assert str(server.last.url).startswith("https://projeto.supabase.co/rest/v1/products")


async def test_service_client_uses_secret_key(
    server: FakePostgrest, alerts: AlertRepository
) -> None:
    server.reply([])
    await alerts.exists_since(PRODUCT_ID, NOW)
    assert server.last.headers["apikey"] == "secreta"


def test_secret_key_is_hidden_in_repr() -> None:
    assert "secreta" not in repr(SETTINGS)


async def test_create_sends_exact_decimals(
    server: FakePostgrest, products: ProductRepository
) -> None:
    server.reply([ROW], 201)
    product = await products.create(new_product())
    assert server.last_body()["target_price"] == "90.10"
    assert product.target_price == Decimal("90.1")
    assert product.current_price == Decimal("100.55")


async def test_create_duplicate(server: FakePostgrest, products: ProductRepository) -> None:
    server.reply({"code": "23505", "message": "duplicate key"}, 409)
    with pytest.raises(DuplicateProductError):
        await products.create(new_product())


async def test_database_error_is_translated(
    server: FakePostgrest, products: ProductRepository
) -> None:
    server.reply({"code": "42501", "message": "permission denied"}, 403)
    with pytest.raises(RepositoryError):
        await products.delete(PRODUCT_ID)


async def test_connection_error_is_translated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = user_client(SETTINGS, http, "jwt")
        client.retry_enabled = False
        with pytest.raises(RepositoryError, match="acessar"):
            await ProductRepository(client).get(PRODUCT_ID)


async def test_list_reads_every_page(server: FakePostgrest, products: ProductRepository) -> None:
    server.reply([ROW] * PAGE_SIZE)
    server.reply([ROW])
    assert len(await products.list_active()) == PAGE_SIZE + 1
    first, second = (request.url.params for request in server.requests)
    assert first["is_active"] == "eq.true"
    assert first.get_list("offset") == ["0"]
    assert second.get_list("offset") == [str(PAGE_SIZE)]


async def test_get_update_and_delete_of_missing_product(
    server: FakePostgrest, products: ProductRepository
) -> None:
    for _ in range(3):
        server.reply([])
    assert await products.get(PRODUCT_ID) is None
    assert await products.update(PRODUCT_ID, ProductUpdate(is_active=False)) is None
    assert await products.delete(PRODUCT_ID) is False


async def test_get_existing(server: FakePostgrest, products: ProductRepository) -> None:
    server.reply([ROW])
    product = await products.get(PRODUCT_ID)
    assert product is not None
    assert product.id == PRODUCT_ID
    assert server.last.url.params["id"] == f"eq.{PRODUCT_ID}"


async def test_update_sends_only_changed_fields(
    server: FakePostgrest, products: ProductRepository
) -> None:
    server.reply([ROW])
    await products.update(PRODUCT_ID, ProductUpdate(is_active=False))
    assert server.last.method == "PATCH"
    assert server.last_body() == {"is_active": False}
    assert server.last.url.params["id"] == f"eq.{PRODUCT_ID}"


async def test_history_filters_by_date(server: FakePostgrest, products: ProductRepository) -> None:
    server.reply([{"price": 10.5, "checked_at": NOW.isoformat()}])
    history = await products.list_history(PRODUCT_ID, NOW)
    assert history[0].price == Decimal("10.5")
    assert server.last.url.params["checked_at"] == f"gte.{NOW.isoformat()}"


@pytest.mark.parametrize(("price", "expected"), [(Decimal("79.90"), "79.90"), (None, None)])
async def test_record_check_calls_database_function(
    server: FakePostgrest, products: ProductRepository, price: Decimal | None, expected: str | None
) -> None:
    # Funções que retornam void respondem 204, sem corpo.
    server.responses.append(httpx.Response(204))
    result = ScrapeResult(
        store=Store.AMAZON_BR,
        title="Fone",
        price=price,
        availability=Availability.OUT_OF_STOCK,
    )
    await products.record_check(PRODUCT_ID, result)
    assert server.last.url.path == "/rest/v1/rpc/record_price_check"
    assert server.last_body()["p_price"] == expected


async def test_record_error_keeps_price(server: FakePostgrest, products: ProductRepository) -> None:
    server.reply([ROW])
    await products.record_error(PRODUCT_ID, "falhou", NOW)
    assert server.last_body() == {"last_error": "falhou", "last_checked_at": NOW.isoformat()}


@pytest.mark.parametrize(("rows", "expected"), [([{"id": 1}], True), ([], False)])
async def test_alert_exists_since(
    server: FakePostgrest, alerts: AlertRepository, rows: list[object], expected: bool
) -> None:
    server.reply(rows)
    assert await alerts.exists_since(PRODUCT_ID, NOW) is expected
    assert server.last.url.params["sent_at"] == f"gte.{NOW.isoformat()}"


async def test_create_alert(server: FakePostgrest, alerts: AlertRepository) -> None:
    server.reply([{}], 201)
    await alerts.create(PRODUCT_ID, Decimal("79.90"))
    assert server.last_body() == {"product_id": str(PRODUCT_ID), "price": "79.90"}


@pytest.mark.parametrize(
    "values", [{}, {"target_price": "0"}, {"target_price": "1.999"}, {"current_price": "1"}]
)
def test_update_rejects_invalid_values(values: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        ProductUpdate.model_validate(values)
