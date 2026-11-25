"""Testa a API inteira, simulando apenas as lojas e o Supabase."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.scrapers.helpers import load_fixture
from tests.tokens import SUPABASE, USER_ID, make_jwks, make_token

PRODUCT_ID = "00000000-0000-0000-0000-000000000001"
URL = "https://www.amazon.com.br/dp/B000000000"
ROW: dict[str, Any] = {
    "id": PRODUCT_ID,
    "user_id": USER_ID,
    "url": URL,
    "store": "amazon_br",
    "title": "Fone",
    "image_url": None,
    "target_price": 90.1,
    "current_price": 100.55,
    "currency": "BRL",
    "is_active": True,
    "last_checked_at": "2026-11-25T12:00:00+00:00",
    "last_error": None,
    "created_at": "2026-11-25T12:00:00+00:00",
}


class World:
    """Estado do Supabase e da loja simulados."""

    def __init__(self) -> None:
        self.store_response = httpx.Response(200, html=load_fixture("amazon_product.html"))
        self.store_urls: list[str] = []
        self.replies: list[httpx.Response] = []
        self.requests: list[httpx.Request] = []
        self.jwks_status = 200

    def reply(self, data: object, status: int = 200) -> None:
        self.replies.append(httpx.Response(status, json=data))

    def handle_store(self, request: httpx.Request) -> httpx.Response:
        self.store_urls.append(str(request.url))
        return self.store_response

    def handle_supabase(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("jwks.json"):
            return httpx.Response(self.jwks_status, json=make_jwks())
        self.requests.append(request)
        return self.replies.pop(0)


@pytest.fixture
def world() -> World:
    return World()


@pytest.fixture
def anonymous(world: World) -> Iterator[TestClient]:
    app = create_app(
        Settings(
            scraper_max_attempts=1,
            scraper_min_interval_seconds=0,
            cors_origins=["http://localhost:5173"],
        ),
        SUPABASE,
        store_transport=httpx.MockTransport(world.handle_store),
        supabase_transport=httpx.MockTransport(world.handle_supabase),
    )
    with TestClient(app) as client:
        yield client


@pytest.fixture
def client(anonymous: TestClient) -> TestClient:
    anonymous.headers["Authorization"] = f"Bearer {make_token()}"
    return anonymous


def create(client: TestClient, url: str = URL, target_price: object = "90.10") -> httpx.Response:
    response: httpx.Response = client.post(
        "/products", json={"url": url, "target_price": target_price}
    )
    return response


def test_health_is_public(anonymous: TestClient) -> None:
    response = anonymous.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/products"),
        ("GET", "/products"),
        ("GET", f"/products/{PRODUCT_ID}"),
        ("PATCH", f"/products/{PRODUCT_ID}"),
        ("DELETE", f"/products/{PRODUCT_ID}"),
        ("GET", f"/products/{PRODUCT_ID}/history"),
    ],
)
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer falso"}])
def test_requires_login(
    anonymous: TestClient, world: World, method: str, path: str, headers: dict[str, str]
) -> None:
    response = anonymous.request(method, path, headers=headers)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert world.requests == []


def test_auth_outage_is_503(client: TestClient, world: World) -> None:
    world.jwks_status = 500
    assert client.get("/products").status_code == 503


def test_create_scrapes_and_saves_as_user(client: TestClient, world: World) -> None:
    world.reply([ROW], 201)
    response = create(client, "http://www.amazon.com.br/dp/B000000000#avaliacoes")
    assert response.status_code == 201
    assert response.json()["id"] == PRODUCT_ID
    assert world.store_urls == [URL]
    request = world.requests[0]
    assert request.headers["apikey"] == "publica"
    assert request.headers["Authorization"] == client.headers["Authorization"]
    body = json.loads(request.content)
    assert body["user_id"] == USER_ID
    assert body["url"] == URL
    assert body["current_price"] == "1289.5"
    assert body["target_price"] == "90.10"


@pytest.mark.parametrize(
    ("url", "target_price"),
    [
        (URL, "0"),
        (URL, "-1"),
        (URL, "1.999"),
        (URL, "abc"),
        ("", "10"),
        ("não é url", "10"),
        ("http://169.254.169.254/", "10"),
        ("https://www.kabum.com.br/x", "10"),
    ],
)
def test_create_rejects_invalid_input(
    client: TestClient, world: World, url: str, target_price: str
) -> None:
    assert create(client, url, target_price).status_code == 422
    assert world.store_urls == []


def test_create_cannot_choose_owner(client: TestClient) -> None:
    body = {"url": URL, "target_price": "10", "user_id": PRODUCT_ID}
    assert client.post("/products", json=body).status_code == 422


@pytest.mark.parametrize(
    ("store_response", "expected"),
    [
        (httpx.Response(404), 422),
        (httpx.Response(403), 502),
        (httpx.Response(500), 502),
        (httpx.Response(200, html="<html></html>"), 502),
    ],
)
def test_create_reports_store_failure(
    client: TestClient, world: World, store_response: httpx.Response, expected: int
) -> None:
    world.store_response = store_response
    response = create(client)
    assert response.status_code == expected
    assert response.json()["detail"]
    assert world.requests == []


def test_create_duplicate(client: TestClient, world: World) -> None:
    world.reply({"code": "23505", "message": "duplicate"}, 409)
    assert create(client).status_code == 409


def test_database_failure_hides_details(client: TestClient, world: World) -> None:
    world.reply({"code": "42501", "message": "segredo interno"}, 403)
    response = client.get("/products")
    assert response.status_code == 503
    assert "segredo" not in response.text


def test_list_and_get(client: TestClient, world: World) -> None:
    world.reply([ROW])
    world.reply([ROW])
    assert [item["id"] for item in client.get("/products").json()] == [PRODUCT_ID]
    assert client.get(f"/products/{PRODUCT_ID}").json()["current_price"] == "100.55"


def test_update(client: TestClient, world: World) -> None:
    world.reply([{**ROW, "is_active": False}])
    response = client.patch(f"/products/{PRODUCT_ID}", json={"is_active": False})
    assert response.status_code == 200
    assert response.json()["is_active"] is False


@pytest.mark.parametrize("body", [{}, {"target_price": 0}, {"current_price": 1}])
def test_update_rejects_invalid_body(client: TestClient, body: dict[str, object]) -> None:
    assert client.patch(f"/products/{PRODUCT_ID}", json=body).status_code == 422


def test_delete(client: TestClient, world: World) -> None:
    world.reply([ROW])
    response = client.delete(f"/products/{PRODUCT_ID}")
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("GET", "", None),
        ("PATCH", "", {"is_active": True}),
        ("DELETE", "", None),
        ("GET", "/history", None),
    ],
)
def test_missing_or_foreign_product_is_404(
    client: TestClient, world: World, method: str, suffix: str, body: object
) -> None:
    world.reply([])
    response = client.request(method, f"/products/{PRODUCT_ID}{suffix}", json=body)
    assert response.status_code == 404


def test_history_uses_requested_period(client: TestClient, world: World) -> None:
    world.reply([ROW])
    world.reply([{"price": 10.5, "checked_at": "2026-11-25T12:00:00+00:00"}])
    response = client.get(f"/products/{PRODUCT_ID}/history", params={"days": 7})
    assert response.json() == [{"price": "10.5", "checked_at": "2026-11-25T12:00:00Z"}]
    since = datetime.fromisoformat(world.requests[1].url.params["checked_at"].removeprefix("gte."))
    assert abs(datetime.now(UTC) - timedelta(days=7) - since) < timedelta(minutes=1)


@pytest.mark.parametrize("days", ["0", "366", "x"])
def test_history_rejects_invalid_period(client: TestClient, days: str) -> None:
    response = client.get(f"/products/{PRODUCT_ID}/history", params={"days": days})
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("origin", "expected"),
    [("http://localhost:5173", "http://localhost:5173"), ("https://evil.com", None)],
)
def test_cors(anonymous: TestClient, origin: str, expected: str | None) -> None:
    response = anonymous.get("/health", headers={"Origin": origin})
    assert response.headers.get("Access-Control-Allow-Origin") == expected
