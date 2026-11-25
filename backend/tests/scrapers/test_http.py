import asyncio

import httpx
import pytest

from app.scrapers.exceptions import (
    BlockedError,
    FetchError,
    InvalidUrlError,
    ProductNotFoundError,
)
from app.scrapers.urls import host_matches, parse_url
from tests.scrapers.helpers import FakeTime, make_fetcher

URL = "https://www.loja.com/produto"
DOMAINS = ("loja.com",)


async def test_retries_temporary_failures_with_growing_backoff() -> None:
    responses = iter([httpx.Response(503), httpx.Response(500), httpx.Response(200, text="ok")])
    time = FakeTime()
    async with make_fetcher(lambda _: next(responses), time) as fetcher:
        response = await fetcher.fetch(URL, DOMAINS)
    assert response.text == "ok"
    first, second = time.sleeps
    assert 1 <= first <= 1.5
    assert 2 <= second <= 3


async def test_gives_up_after_max_attempts() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectTimeout("timeout", request=request)

    async with make_fetcher(handler) as fetcher:
        with pytest.raises(FetchError, match="demorou"):
            await fetcher.fetch(URL, DOMAINS)
    assert calls == 3


@pytest.mark.parametrize(("header", "expected"), [("10", 10), ("9999", 30)])
async def test_respects_retry_after_up_to_limit(header: str, expected: float) -> None:
    responses = iter([httpx.Response(429, headers={"Retry-After": header}), httpx.Response(200)])
    time = FakeTime()
    async with make_fetcher(lambda _: next(responses), time) as fetcher:
        await fetcher.fetch(URL, DOMAINS)
    assert time.sleeps == [expected]


@pytest.mark.parametrize(
    ("status", "error"),
    [(404, ProductNotFoundError), (403, BlockedError), (202, BlockedError), (400, FetchError)],
)
async def test_does_not_retry_permanent_failures(status: int, error: type[FetchError]) -> None:
    time = FakeTime()
    async with make_fetcher(lambda _: httpx.Response(status), time) as fetcher:
        with pytest.raises(error):
            await fetcher.fetch(URL, DOMAINS)
    assert time.sleeps == []


async def test_follows_redirect_inside_store() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/produto":
            return httpx.Response(301, headers={"Location": "/novo"})
        return httpx.Response(200, text="novo")

    async with make_fetcher(handler) as fetcher:
        assert (await fetcher.fetch(URL, DOMAINS)).text == "novo"


async def test_refuses_redirect_to_other_domain() -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.host)
        return httpx.Response(302, headers={"Location": "http://169.254.169.254/"})

    async with make_fetcher(handler) as fetcher:
        with pytest.raises(FetchError, match="domínio"):
            await fetcher.fetch(URL, DOMAINS)
    assert requested == ["www.loja.com"]


async def test_redirect_loop_is_an_error() -> None:
    async with make_fetcher(lambda _: httpx.Response(302, headers={"Location": URL})) as fetcher:
        with pytest.raises(FetchError, match="vezes demais"):
            await fetcher.fetch(URL, DOMAINS)


async def test_spaces_concurrent_requests_to_same_host() -> None:
    time = FakeTime()
    async with make_fetcher(lambda _: httpx.Response(200), time, min_interval=2) as fetcher:
        await asyncio.gather(*(fetcher.fetch(URL, DOMAINS) for _ in range(3)))
    assert time.sleeps == [2, 2]


async def test_does_not_keep_cookies() -> None:
    cookies: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        cookies.append(request.headers.get("Cookie"))
        return httpx.Response(200, headers={"Set-Cookie": "sessao=1; Path=/"})

    async with make_fetcher(handler) as fetcher:
        await fetcher.fetch(URL, DOMAINS)
        await fetcher.fetch(URL, DOMAINS)
    assert cookies == [None, None]


async def test_sends_realistic_user_agent() -> None:
    agents: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        agents.append(request.headers["User-Agent"])
        return httpx.Response(200)

    async with make_fetcher(handler) as fetcher:
        await fetcher.fetch(URL, DOMAINS)
    assert agents[0].startswith("Mozilla/5.0")


@pytest.mark.parametrize(
    "url",
    ["", "loja.com/x", "ftp://loja.com", "https://", "https://u:p@loja.com", "https://loja.com:99"],
)
def test_parse_url_rejects_invalid(url: str) -> None:
    with pytest.raises(InvalidUrlError):
        parse_url(url)


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("loja.com", True),
        ("WWW.loja.com", True),
        ("fakeloja.com", False),
        ("loja.com.evil.com", False),
    ],
)
def test_host_matches(host: str, expected: bool) -> None:
    assert host_matches(host, DOMAINS) is expected
