"""Validação dos tokens do Supabase Auth com as chaves públicas do projeto (JWKS)."""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

import httpx
import jwt

from app.core.config import SupabaseSettings

_ALGORITHMS = ["ES256", "RS256"]
_CACHE_SECONDS = 600.0
# Evita que tokens com `kid` inventado provoquem uma busca de chaves por requisição.
_REFRESH_COOLDOWN_SECONDS = 30.0


class InvalidTokenError(Exception):
    """O token é inválido, expirou ou não pertence a este projeto."""


class AuthUnavailableError(Exception):
    """As chaves do Supabase não puderam ser obtidas."""


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    access_token: str


class TokenVerifier:
    def __init__(
        self,
        settings: SupabaseSettings,
        http: httpx.AsyncClient,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._issuer = f"{settings.url.rstrip('/')}/auth/v1"
        self._http = http
        self._clock = clock
        self._lock = asyncio.Lock()
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at: float | None = None

    async def verify(self, token: str) -> AuthenticatedUser:
        """Valida o token e identifica o usuário.

        Raises:
            InvalidTokenError: se o token não for aceito.
            AuthUnavailableError: se as chaves estiverem inacessíveis.
        """
        try:
            key = await self._get_key(jwt.get_unverified_header(token).get("kid"))
            claims = jwt.decode(
                token,
                key,
                algorithms=_ALGORITHMS,
                audience="authenticated",
                issuer=self._issuer,
                leeway=10,
                options={"require": ["exp", "sub", "aud", "iss"]},
            )
            return AuthenticatedUser(id=UUID(claims["sub"]), access_token=token)
        except (jwt.PyJWTError, ValueError) as error:
            raise InvalidTokenError("Sessão inválida ou expirada.") from error

    async def _get_key(self, kid: object) -> jwt.PyJWK:
        if not isinstance(kid, str):
            raise InvalidTokenError("Sessão inválida ou expirada.")
        async with self._lock:
            age = None if self._fetched_at is None else self._clock() - self._fetched_at
            is_stale = age is None or age >= _CACHE_SECONDS
            is_unknown = kid not in self._keys
            if is_stale or (is_unknown and age is not None and age >= _REFRESH_COOLDOWN_SECONDS):
                await self._refresh()
        key = self._keys.get(kid)
        if key is None:
            raise InvalidTokenError("Sessão inválida ou expirada.")
        return key

    async def _refresh(self) -> None:
        try:
            response = await self._http.get(f"{self._issuer}/.well-known/jwks.json")
            response.raise_for_status()
            key_set = jwt.PyJWKSet.from_dict(response.json())
        except (httpx.HTTPError, ValueError, AttributeError, jwt.PyJWTError) as error:
            raise AuthUnavailableError("Autenticação temporariamente indisponível.") from error
        self._keys = {key.key_id: key for key in key_set.keys if key.key_id}
        self._fetched_at = self._clock()
