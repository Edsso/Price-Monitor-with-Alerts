import time
from uuid import UUID

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.core.auth import AuthUnavailableError, InvalidTokenError, TokenVerifier
from tests.tokens import SUPABASE, USER_ID, make_jwks, make_token


class JwksServer:
    def __init__(self) -> None:
        self.calls = 0
        self.kid = "k1"
        self.status = 200
        self.now = 0.0

    def handle(self, request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/v1/.well-known/jwks.json"
        self.calls += 1
        return httpx.Response(self.status, json=make_jwks(self.kid))

    def verifier(self) -> TokenVerifier:
        http = httpx.AsyncClient(transport=httpx.MockTransport(self.handle))
        return TokenVerifier(SUPABASE, http, clock=lambda: self.now)


async def test_accepts_valid_token_and_caches_keys() -> None:
    server = JwksServer()
    verifier = server.verifier()
    token = make_token()
    user = await verifier.verify(token)
    await verifier.verify(token)
    assert user.id == UUID(USER_ID)
    assert user.access_token == token
    assert server.calls == 1


@pytest.mark.parametrize(
    "token",
    [
        "não é um jwt",
        make_token(exp=int(time.time()) - 60),
        make_token(aud="anon"),
        make_token(iss="https://outro.supabase.co/auth/v1"),
        make_token(sub="não é uuid"),
        make_token(remove="sub"),
        make_token(remove="exp"),
        make_token(key=ec.generate_private_key(ec.SECP256R1())),
        make_token(kid="desconhecido"),
    ],
)
async def test_rejects_invalid_token(token: str) -> None:
    with pytest.raises(InvalidTokenError):
        await JwksServer().verifier().verify(token)


@pytest.mark.parametrize("algorithm", ["none", "HS256"])
async def test_rejects_other_algorithms(algorithm: str) -> None:
    key = "" if algorithm == "none" else "x" * 32
    token = jwt.encode({"sub": USER_ID}, key, algorithm=algorithm, headers={"kid": "k1"})
    with pytest.raises(InvalidTokenError):
        await JwksServer().verifier().verify(token)


async def test_unknown_key_refreshes_only_after_cooldown() -> None:
    server = JwksServer()
    verifier = server.verifier()
    await verifier.verify(make_token())
    server.kid = "k2"
    with pytest.raises(InvalidTokenError):
        await verifier.verify(make_token(kid="k2"))
    assert server.calls == 1
    server.now = 31
    await verifier.verify(make_token(kid="k2"))
    assert server.calls == 2


async def test_reports_unavailable_keys() -> None:
    server = JwksServer()
    server.status = 500
    with pytest.raises(AuthUnavailableError):
        await server.verifier().verify(make_token())
