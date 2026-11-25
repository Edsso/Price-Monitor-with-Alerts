"""Acesso ao PostgREST do Supabase."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import httpx
from postgrest import APIError, AsyncPostgrestClient

from app.core.config import SupabaseSettings
from app.repositories.exceptions import DuplicateProductError, RepositoryError

PAGE_SIZE = 1000  # limite padrão de linhas por resposta no Supabase
_UNIQUE_VIOLATION = "23505"

Row = dict[str, Any]


def user_client(
    settings: SupabaseSettings, http: httpx.AsyncClient, access_token: str
) -> AsyncPostgrestClient:
    """Cliente que age em nome do usuário, sujeito a RLS."""
    return _client(settings, http, settings.publishable_key, access_token)


def service_client(settings: SupabaseSettings, http: httpx.AsyncClient) -> AsyncPostgrestClient:
    """Cliente que ignora RLS; uso exclusivo do job."""
    key = settings.secret_key.get_secret_value()
    return _client(settings, http, key, key)


def _client(
    settings: SupabaseSettings, http: httpx.AsyncClient, api_key: str, token: str
) -> AsyncPostgrestClient:
    return AsyncPostgrestClient(
        f"{settings.url.rstrip('/')}/rest/v1",
        headers={"apikey": api_key, "Authorization": f"Bearer {token}"},
        http_client=http,
    )


async def execute(query: Any) -> list[Row]:
    """Executa a consulta e devolve as linhas, traduzindo os erros."""
    with _translate_errors():
        response = await query.execute()
    data = response.data
    return data if isinstance(data, list) else []


async def fetch_all(build_query: Callable[[], Any]) -> list[Row]:
    """Lê todas as páginas de uma consulta, que precisa ter ordenação estável.

    Recebe uma função porque o builder é mutável: reutilizá-lo acumularia os limites.
    """
    rows: list[Row] = []
    while True:
        page = await execute(build_query().range(len(rows), len(rows) + PAGE_SIZE - 1))
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows


@contextmanager
def _translate_errors() -> Iterator[None]:
    try:
        yield
    except APIError as error:
        if error.code == _UNIQUE_VIOLATION:
            raise DuplicateProductError("Este produto já está cadastrado.") from error
        raise RepositoryError("O banco de dados recusou a operação.") from error
    except httpx.HTTPError as error:
        raise RepositoryError("Não foi possível acessar o banco de dados.") from error
