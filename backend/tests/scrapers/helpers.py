"""Utilitários para testar scrapers sem acessar a internet."""

from collections.abc import Callable
from pathlib import Path

import httpx

from app.core.config import Settings
from app.scrapers.http import PageFetcher

FIXTURES = Path(__file__).parent.parent / "fixtures"
Handler = Callable[[httpx.Request], httpx.Response]


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeTime:
    """Relógio controlado: dormir apenas avança o tempo."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_fetcher(
    handler: Handler,
    fake_time: FakeTime | None = None,
    *,
    max_attempts: int = 3,
    min_interval: float = 0,
) -> PageFetcher:
    fake_time = fake_time or FakeTime()
    settings = Settings(
        scraper_max_attempts=max_attempts,
        scraper_backoff_seconds=1,
        scraper_min_interval_seconds=min_interval,
    )
    return PageFetcher(
        settings,
        transport=httpx.MockTransport(handler),
        sleep=fake_time.sleep,
        clock=fake_time.clock,
    )


def serve(html: str) -> Handler:
    return lambda request: httpx.Response(200, html=html)
