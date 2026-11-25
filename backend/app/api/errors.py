"""Conversão dos erros da aplicação em respostas HTTP, no formato `{"detail": ...}`."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.auth import AuthUnavailableError, InvalidTokenError
from app.repositories.exceptions import DuplicateProductError, RepositoryError
from app.scrapers.exceptions import (
    InvalidUrlError,
    ProductNotFoundError,
    ScraperError,
    UnsupportedStoreError,
)
from app.services.products import ProductNotRegisteredError

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidTokenError)
    async def invalid_token(_: Request, error: InvalidTokenError) -> JSONResponse:
        return _response(401, str(error), {"WWW-Authenticate": "Bearer"})

    @app.exception_handler(AuthUnavailableError)
    async def auth_unavailable(_: Request, error: AuthUnavailableError) -> JSONResponse:
        logger.error("Falha ao obter as chaves de autenticação", exc_info=error)
        return _response(503, str(error))

    @app.exception_handler(ProductNotRegisteredError)
    async def not_registered(_: Request, error: ProductNotRegisteredError) -> JSONResponse:
        return _response(404, "Produto não encontrado.")

    @app.exception_handler(ScraperError)
    async def scraper_error(_: Request, error: ScraperError) -> JSONResponse:
        # A URL é problema de quem enviou; o resto é falha da loja.
        is_bad_url = isinstance(
            error, InvalidUrlError | UnsupportedStoreError | ProductNotFoundError
        )
        return _response(422 if is_bad_url else 502, str(error))

    @app.exception_handler(RepositoryError)
    async def repository_error(_: Request, error: RepositoryError) -> JSONResponse:
        if isinstance(error, DuplicateProductError):
            return _response(409, str(error))
        logger.error("Falha no banco de dados", exc_info=error)
        return _response(503, "Serviço temporariamente indisponível.")


def _response(code: int, detail: str, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=code, headers=headers)
