"""Validação de URLs e domínios."""

import httpx

from app.scrapers.exceptions import InvalidUrlError


def parse_url(url: str) -> httpx.URL:
    """Valida uma URL de produto, exigindo HTTP(S), porta padrão e nenhuma credencial."""
    try:
        parsed = httpx.URL(url.strip())
    except (httpx.InvalidURL, ValueError) as error:
        raise InvalidUrlError("URL inválida.") from error
    if parsed.scheme not in {"http", "https"} or not parsed.host:
        raise InvalidUrlError("A URL precisa começar com http:// ou https://.")
    if parsed.userinfo or parsed.port is not None:
        raise InvalidUrlError("A URL não pode conter usuário, senha ou porta.")
    return parsed


def host_matches(host: str, domains: tuple[str, ...]) -> bool:
    """Indica se `host` é um dos domínios ou subdomínio deles."""
    host = host.lower().rstrip(".")
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)
