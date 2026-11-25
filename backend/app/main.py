"""Montagem da aplicação FastAPI.

Uso: uvicorn app.main:create_app --factory --reload
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, products
from app.api.dependencies import Resources
from app.api.errors import register_error_handlers
from app.core.auth import TokenVerifier
from app.core.config import Settings, SupabaseSettings, get_settings
from app.scrapers.http import PageFetcher

_SUPABASE_TIMEOUT_SECONDS = 10.0


def create_app(
    settings: Settings | None = None,
    supabase: SupabaseSettings | None = None,
    *,
    store_transport: httpx.AsyncBaseTransport | None = None,
    supabase_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """Cria a aplicação. Os transportes permitem testar sem acessar a internet."""
    settings = settings or get_settings()
    supabase = supabase or SupabaseSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with (
            httpx.AsyncClient(
                transport=supabase_transport, timeout=_SUPABASE_TIMEOUT_SECONDS
            ) as http,
            PageFetcher(settings, transport=store_transport) as fetcher,
        ):
            app.state.resources = Resources(
                supabase=supabase,
                http=http,
                fetcher=fetcher,
                verifier=TokenVerifier(supabase, http),
            )
            yield

    app = FastAPI(title="Monitor de Preços", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(products.router)
    return app
