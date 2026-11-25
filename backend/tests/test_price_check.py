"""Testa o job inteiro com um Supabase em memória e lojas simuladas."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from app.models.product import Product
from app.repositories.alerts import AlertRepository
from app.repositories.client import service_client
from app.repositories.products import ProductRepository
from app.repositories.users import UserRepository
from app.services.email import EmailError
from app.services.price_check import PriceCheckJob
from tests.scrapers.helpers import load_fixture, make_fetcher
from tests.tokens import SUPABASE, USER_ID

NOW = datetime(2026, 11, 25, 12, tzinfo=UTC)
PRICE = "1289.5"  # preço da fixture da Amazon
A = "00000000-0000-0000-0000-000000000001"
B = "00000000-0000-0000-0000-000000000002"


class FakeSupabase:
    def __init__(self) -> None:
        self.products: dict[str, dict[str, Any]] = {}
        self.alerts: list[dict[str, Any]] = []
        self.history: list[tuple[str, Any]] = []
        self.user_status = 200
        self.fail_listing = False
        self.fail_check_of: str | None = None
        self.after_check: Callable[[], None] = lambda: None

    def add(self, product_id: str, **overrides: Any) -> None:
        self.products[product_id] = {
            "id": product_id,
            "user_id": USER_ID,
            "url": f"https://www.amazon.com.br/dp/{product_id}",
            "store": "amazon_br",
            "title": "Fone",
            "image_url": None,
            "target_price": 1500,
            "current_price": 2000,
            "currency": "BRL",
            "is_active": True,
            "last_checked_at": None,
            "last_error": "erro antigo",
            "created_at": NOW.isoformat(),
            **overrides,
        }

    def handle(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["apikey"] == "secreta"
        path, params = request.url.path, request.url.params
        body = json.loads(request.content) if request.content else {}
        if path.startswith("/auth/v1/admin/users/"):
            assert path.endswith(USER_ID)
            return httpx.Response(self.user_status, json={"email": "ana@exemplo.com"})
        if path.endswith("/rpc/record_price_check"):
            return self._record_check(body)
        if path.endswith("/alerts"):
            return self._alerts(request.method, params, body)
        if request.method == "PATCH":
            self.products[params["id"].removeprefix("eq.")].update(body)
            return httpx.Response(200, json=[])
        if self.fail_listing:
            return httpx.Response(403, json={"code": "42501", "message": "negado"})
        if "id" in params:
            row = self.products.get(params["id"].removeprefix("eq."))
            return httpx.Response(200, json=[row] if row else [])
        return httpx.Response(200, json=[p for p in self.products.values() if p["is_active"]])

    def _record_check(self, body: dict[str, Any]) -> httpx.Response:
        product_id = body["p_product_id"]
        if product_id == self.fail_check_of:
            return httpx.Response(403, json={"code": "42501", "message": "negado"})
        if product_id in self.products:
            self.products[product_id].update(current_price=body["p_price"], last_error=None)
            self.history.append((product_id, body["p_price"]))
        self.after_check()
        return httpx.Response(204)

    def _alerts(self, method: str, params: httpx.QueryParams, body: Any) -> httpx.Response:
        if method == "POST":
            self.alerts.append({**body, "sent_at": NOW})
            return httpx.Response(201, json=[body])
        since = datetime.fromisoformat(params["sent_at"].removeprefix("gte."))
        product_id = params["product_id"].removeprefix("eq.")
        found = [a for a in self.alerts if a["product_id"] == product_id and a["sent_at"] >= since]
        return httpx.Response(200, json=[{"id": 1} for _ in found])


class FakeSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.error: Exception | None = None
        self.wait: Callable[[], Awaitable[object]] | None = None

    async def send_alert(self, recipient: str, product: Product) -> None:
        if self.wait:
            await self.wait()
        if self.error:
            raise self.error
        self.sent.append((recipient, str(product.id)))


class Scenario:
    def __init__(self) -> None:
        self.db = FakeSupabase()
        self.sender = FakeSender()
        self.store: Callable[[httpx.Request], httpx.Response] = lambda _: httpx.Response(
            200, html=load_fixture("amazon_product.html")
        )

    def build(self) -> PriceCheckJob:
        http = httpx.AsyncClient(transport=httpx.MockTransport(self.db.handle))
        service = service_client(SUPABASE, http)
        return PriceCheckJob(
            products=ProductRepository(service),
            alerts=AlertRepository(service),
            users=UserRepository(SUPABASE, http),
            fetcher=make_fetcher(lambda request: self.store(request), max_attempts=1),
            sender=self.sender,
            alert_interval=timedelta(hours=24),
            now=lambda: NOW,
        )

    async def run(self) -> None:
        await self.build().run()


@pytest.fixture
def scenario() -> Scenario:
    return Scenario()


async def test_saves_price_sends_and_records_alert(scenario: Scenario) -> None:
    scenario.db.add(A)
    await scenario.run()
    assert scenario.db.history == [(A, PRICE)]
    assert scenario.db.products[A]["last_error"] is None
    assert scenario.sender.sent == [("ana@exemplo.com", A)]
    assert scenario.db.alerts[0]["price"] == PRICE


@pytest.mark.parametrize(
    "overrides", [{"target_price": 1000}, {"is_active": False}], ids=["acima do alvo", "pausado"]
)
async def test_does_not_alert(scenario: Scenario, overrides: dict[str, Any]) -> None:
    scenario.db.add(A, **overrides)
    await scenario.run()
    assert scenario.sender.sent == []


async def test_out_of_stock_does_not_alert(scenario: Scenario) -> None:
    scenario.db.add(A, current_price=100)
    scenario.store = lambda _: httpx.Response(200, html=load_fixture("amazon_unavailable.html"))
    await scenario.run()
    assert scenario.db.products[A]["current_price"] is None
    assert scenario.sender.sent == []


@pytest.mark.parametrize(("hours", "expected"), [(23, 0), (24, 0), (25, 1)])
async def test_respects_24h_between_alerts(scenario: Scenario, hours: int, expected: int) -> None:
    scenario.db.add(A)
    scenario.db.alerts.append({"product_id": A, "sent_at": NOW - timedelta(hours=hours)})
    await scenario.run()
    assert len(scenario.sender.sent) == expected


async def test_recent_alert_of_other_product_does_not_block(scenario: Scenario) -> None:
    scenario.db.add(A)
    scenario.db.alerts.append({"product_id": B, "sent_at": NOW})
    await scenario.run()
    assert len(scenario.sender.sent) == 1


async def test_store_failure_does_not_stop_others(scenario: Scenario) -> None:
    scenario.db.add(A)
    scenario.db.add(B)
    ok = scenario.store
    scenario.store = lambda r: httpx.Response(403) if r.url.path.endswith(A) else ok(r)
    await scenario.run()
    assert "bloqueou" in scenario.db.products[A]["last_error"]
    assert scenario.db.products[A]["current_price"] == 2000
    assert scenario.sender.sent == [("ana@exemplo.com", B)]


async def test_unsupported_store_does_not_stop_others(scenario: Scenario) -> None:
    scenario.db.add(A, url="https://www.kabum.com.br/x")
    scenario.db.add(B)
    await scenario.run()
    assert "não suportada" in scenario.db.products[A]["last_error"]
    assert len(scenario.sender.sent) == 1


async def test_database_failure_does_not_stop_others(scenario: Scenario) -> None:
    scenario.db.add(A)
    scenario.db.add(B)
    scenario.db.fail_check_of = A
    await scenario.run()
    assert "inesperado" in scenario.db.products[A]["last_error"]
    assert scenario.sender.sent == [("ana@exemplo.com", B)]


async def test_email_failure_is_recorded_and_retried_later(scenario: Scenario) -> None:
    scenario.db.add(A)
    scenario.sender.error = EmailError("Não foi possível enviar o e-mail de alerta.")
    await scenario.run()
    assert "e-mail" in scenario.db.products[A]["last_error"]
    assert scenario.db.products[A]["current_price"] == PRICE
    assert scenario.db.alerts == []
    scenario.sender.error = None
    await scenario.run()
    assert len(scenario.db.alerts) == 1


async def test_user_lookup_failure_is_recorded(scenario: Scenario) -> None:
    scenario.db.add(A)
    scenario.db.user_status = 500
    await scenario.run()
    assert scenario.db.products[A]["last_error"]
    assert scenario.sender.sent == []


async def test_uses_target_changed_during_job(scenario: Scenario) -> None:
    scenario.db.add(A)
    scenario.db.after_check = lambda: scenario.db.products[A].update(target_price=1)
    await scenario.run()
    assert scenario.sender.sent == []


async def test_product_deleted_during_job_is_ignored(scenario: Scenario) -> None:
    scenario.db.add(A)
    scenario.db.after_check = scenario.db.products.clear
    await scenario.run()
    assert scenario.sender.sent == []


async def test_listing_failure_does_not_raise(scenario: Scenario) -> None:
    scenario.db.fail_listing = True
    await scenario.run()


async def test_simultaneous_runs_send_a_single_alert(scenario: Scenario) -> None:
    scenario.db.add(A)
    started, release = asyncio.Event(), asyncio.Event()

    async def wait() -> None:
        started.set()
        await release.wait()

    scenario.sender.wait = wait
    job = scenario.build()
    first = asyncio.create_task(job.run())
    await started.wait()
    await job.run()
    release.set()
    await first
    assert len(scenario.sender.sent) == 1
    assert len(scenario.db.history) == 1
