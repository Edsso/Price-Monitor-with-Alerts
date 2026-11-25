"""Cliente HTTP dos scrapers: timeout, retry com backoff e intervalo entre requisições."""

import asyncio
import random
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from types import TracebackType
from typing import Self

import httpx

from app.core.config import Settings
from app.scrapers.exceptions import BlockedError, FetchError, ProductNotFoundError
from app.scrapers.urls import host_matches, parse_url

MAX_REDIRECTS = 5
MAX_RETRY_DELAY_SECONDS = 30.0

Sleep = Callable[[float], Awaitable[None]]
Clock = Callable[[], float]


class _RetryableError(Exception):
    def __init__(self, error: FetchError, retry_after: float = 0.0) -> None:
        super().__init__(str(error))
        self.error = error
        self.retry_after = retry_after


class PageFetcher:
    """Baixa páginas HTML. Uma instância deve ser compartilhada por toda a execução."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
        clock: Clock = time.monotonic,
    ) -> None:
        self._settings = settings
        self._sleep = sleep
        self._clock = clock
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._last_request: dict[str, float] = {}
        self._client = httpx.AsyncClient(
            transport=transport,
            timeout=settings.scraper_timeout_seconds,
            follow_redirects=False,
            headers={
                "User-Agent": settings.scraper_user_agent,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
            },
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self._client.aclose()

    async def fetch(self, url: str, allowed_domains: tuple[str, ...]) -> httpx.Response:
        """Baixa `url`, repetindo falhas temporárias.

        Raises:
            InvalidUrlError: se a URL for inválida.
            FetchError: se a página não puder ser baixada.
        """
        attempt = 1
        while True:
            try:
                return await self._fetch_following_redirects(url, allowed_domains)
            except _RetryableError as failure:
                if attempt >= self._settings.scraper_max_attempts:
                    raise failure.error from failure
                backoff = self._settings.scraper_backoff_seconds * 2 ** (attempt - 1)
                jitter = random.uniform(0, backoff / 2)  # noqa: S311 - não é uso criptográfico
                delay = max(backoff + jitter, failure.retry_after)
                await self._sleep(min(delay, MAX_RETRY_DELAY_SECONDS))
                attempt += 1

    async def _fetch_following_redirects(
        self, url: str, allowed_domains: tuple[str, ...]
    ) -> httpx.Response:
        current = parse_url(url)
        for _ in range(MAX_REDIRECTS + 1):
            # Validar cada salto impede que um redirecionamento alcance a rede interna (SSRF).
            if not host_matches(current.host, allowed_domains):
                raise FetchError("A loja redirecionou para um domínio não permitido.")
            response = await self._request(current)
            if response.next_request is None:
                _raise_for_status(response)
                return response
            current = parse_url(str(response.next_request.url))
        raise FetchError("A loja redirecionou a página vezes demais.")

    async def _request(self, url: httpx.URL) -> httpx.Response:
        await self._wait_turn(url.host)
        try:
            return await self._client.get(url)
        except httpx.TimeoutException as error:
            raise _RetryableError(FetchError("A loja demorou demais para responder.")) from error
        except httpx.HTTPError as error:
            raise _RetryableError(FetchError("Não foi possível conectar à loja.")) from error

    async def _wait_turn(self, host: str) -> None:
        async with self._locks[host]:
            last = self._last_request.get(host)
            if last is not None:
                wait = last + self._settings.scraper_min_interval_seconds - self._clock()
                if wait > 0:
                    await self._sleep(wait)
            self._last_request[host] = self._clock()


def _raise_for_status(response: httpx.Response) -> None:
    status = response.status_code
    if status == httpx.codes.OK:
        return
    if status in {httpx.codes.NOT_FOUND, httpx.codes.GONE}:
        raise ProductNotFoundError("Produto não encontrado na loja.")
    if status == httpx.codes.TOO_MANY_REQUESTS:
        raise _RetryableError(
            BlockedError("A loja limitou o número de acessos."), _retry_after(response)
        )
    if status in {httpx.codes.ACCEPTED, httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN}:
        # 202 é usado por firewalls para entregar um desafio no lugar da página.
        raise BlockedError("A loja bloqueou o acesso automático.")
    error = FetchError(f"A loja respondeu com o erro HTTP {status}.")
    if status >= httpx.codes.INTERNAL_SERVER_ERROR:
        raise _RetryableError(error, _retry_after(response))
    raise error


def _retry_after(response: httpx.Response) -> float:
    value = response.headers.get("Retry-After", "")
    return float(value) if value.isascii() and value.isdigit() else 0.0
