"""Dependências injetadas nas rotas."""

from dataclasses import dataclass
from typing import Annotated, cast

import httpx
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import AuthenticatedUser, InvalidTokenError, TokenVerifier
from app.core.config import SupabaseSettings
from app.repositories.client import user_client
from app.repositories.products import ProductRepository
from app.scrapers.http import PageFetcher
from app.services.products import ProductService

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Resources:
    """Recursos que vivem enquanto a aplicação estiver no ar."""

    supabase: SupabaseSettings
    http: httpx.AsyncClient
    fetcher: PageFetcher
    verifier: TokenVerifier


def get_resources(request: Request) -> Resources:
    return cast(Resources, request.app.state.resources)


ResourcesDep = Annotated[Resources, Depends(get_resources)]


async def get_current_user(
    resources: ResourcesDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AuthenticatedUser:
    if credentials is None:
        raise InvalidTokenError("Faça login para continuar.")
    return await resources.verifier.verify(credentials.credentials)


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


def get_product_service(resources: ResourcesDep, user: CurrentUser) -> ProductService:
    client = user_client(resources.supabase, resources.http, user.access_token)
    return ProductService(ProductRepository(client), resources.fetcher)


ProductServiceDep = Annotated[ProductService, Depends(get_product_service)]
