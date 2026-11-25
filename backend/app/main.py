"""Montagem da aplicação FastAPI.

Uso: uvicorn app.main:create_app --factory --reload
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, jobs, products
from app.api.dependencies import Resources
from app.api.errors import register_error_handlers
from app.core.auth import TokenVerifier
from app.core.config import JobSettings, Settings, SupabaseSettings, get_settings
from app.repositories.alerts import AlertRepository
from app.repositories.client import service_client
from app.repositories.products import ProductRepository
from app.repositories.users import UserRepository
from app.scrapers.http import PageFetcher
from app.services.email import AlertSender, ResendAlertSender
from app.services.price_check import PriceCheckJob

_SUPABASE_TIMEOUT_SECONDS = 10.0


def create_app(
    settings: Settings | None = None,
    supabase: SupabaseSettings | None = None,
    job_settings: JobSettings | None = None,
    *,
    store_transport: httpx.AsyncBaseTransport | None = None,
    supabase_transport: httpx.AsyncBaseTransport | None = None,
    sender: AlertSender | None = None,
) -> FastAPI:
    """Cria a aplicação. Os transportes e `sender` permitem testar sem acessar a internet."""
    settings = settings or get_settings()
    supabase = supabase or SupabaseSettings()
    job_settings = job_settings or JobSettings()
    sender = sender or ResendAlertSender(job_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with (
            httpx.AsyncClient(
                transport=supabase_transport, timeout=_SUPABASE_TIMEOUT_SECONDS
            ) as http,
            PageFetcher(settings, transport=store_transport) as fetcher,
        ):
            service = service_client(supabase, http)
            app.state.resources = Resources(
                supabase=supabase,
                http=http,
                fetcher=fetcher,
                verifier=TokenVerifier(supabase, http),
                cron_secret=job_settings.cron_secret,
                job=PriceCheckJob(
                    products=ProductRepository(service),
                    alerts=AlertRepository(service),
                    users=UserRepository(supabase, http),
                    fetcher=fetcher,
                    sender=sender,
                    alert_interval=timedelta(hours=job_settings.alert_interval_hours),
                ),
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
    app.include_router(jobs.router)
    return app
