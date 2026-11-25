"""Diagnóstico: verifica quais endpoints do Mercado Livre devolvem preço para o seu app.

Uso (na pasta backend): python scripts/probe_mercado_livre.py <url do produto>
Lê MERCADO_LIVRE_CLIENT_ID e MERCADO_LIVRE_CLIENT_SECRET do `.env`. Nunca imprime o token.
"""

import re
import sys

import httpx
from pydantic import SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

API_URL = "https://api.mercadolibre.com"


class Credentials(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MERCADO_LIVRE_", extra="ignore")

    client_id: str
    client_secret: SecretStr


def build_paths(url: str) -> list[str]:
    """Monta os endpoints a testar: produto de catálogo (`/p/MLB1`) ou anúncio (`MLB-1`)."""
    if match := re.search(r"/p/MLB(\d+)", url):
        return [f"/products/MLB{match[1]}", f"/products/MLB{match[1]}/items"]
    if match := re.search(r"MLB-?(\d+)", url):
        return [f"/items/MLB{match[1]}", f"/items/MLB{match[1]}/prices"]
    return []


def find_price(data: object) -> object:
    """Procura o primeiro preço nos formatos conhecidos da API."""
    if not isinstance(data, dict):
        return None
    if data.get("price") is not None:
        return data["price"]
    winner = data.get("buy_box_winner")
    if isinstance(winner, dict) and winner.get("price") is not None:
        return winner["price"]
    for key, field in (("results", "price"), ("prices", "amount")):
        entries = data.get(key)
        if isinstance(entries, list) and entries and isinstance(entries[0], dict):
            return entries[0].get(field)
    return None


def main() -> int:
    paths = build_paths(sys.argv[1]) if len(sys.argv) == 2 else []
    if not paths:
        print("Informe a URL de um produto do Mercado Livre.", file=sys.stderr)
        return 1
    try:
        credentials = Credentials()
    except ValidationError:
        print("Defina MERCADO_LIVRE_CLIENT_ID e _CLIENT_SECRET no .env.", file=sys.stderr)
        return 1
    try:
        with httpx.Client(base_url=API_URL, timeout=20) as client:
            response = client.post(
                "/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": credentials.client_id,
                    "client_secret": credentials.client_secret.get_secret_value(),
                },
            )
            if response.is_error:
                # Só o código do erro: o corpo completo poderia conter dados sensíveis.
                print(f"Falha na autenticação: HTTP {response.status_code}", file=sys.stderr)
                return 1
            headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
            found = False
            for path in paths:
                response = client.get(path, headers=headers)
                price = find_price(response.json()) if response.is_success else None
                found = found or price is not None
                print(f"{path}: HTTP {response.status_code}, preço: {price}")
    except (httpx.HTTPError, ValueError, KeyError) as error:
        print(f"Falha ao consultar a API: {type(error).__name__}", file=sys.stderr)
        return 1
    print("Resultado: a API libera o preço." if found else "Resultado: nenhum preço liberado.")
    return 0 if found else 2


if __name__ == "__main__":
    sys.exit(main())
