"""Consulta de usuários no Supabase Auth (somente job)."""

from uuid import UUID

import httpx

from app.core.config import SupabaseSettings
from app.repositories.exceptions import RepositoryError


class UserRepository:
    def __init__(self, settings: SupabaseSettings, http: httpx.AsyncClient) -> None:
        self._url = f"{settings.url.rstrip('/')}/auth/v1/admin/users"
        self._key = settings.secret_key
        self._http = http

    async def get_email(self, user_id: UUID) -> str:
        """Obtém o e-mail do usuário.

        Raises:
            RepositoryError: se o usuário não puder ser consultado ou não tiver e-mail.
        """
        key = self._key.get_secret_value()
        headers = {"apikey": key, "Authorization": f"Bearer {key}"}
        try:
            response = await self._http.get(f"{self._url}/{user_id}", headers=headers)
            response.raise_for_status()
            email = response.json().get("email")
        except (httpx.HTTPError, ValueError, AttributeError) as error:
            raise RepositoryError("Não foi possível consultar o usuário.") from error
        if not isinstance(email, str) or not email:
            raise RepositoryError("O usuário não tem e-mail.")
        return email
