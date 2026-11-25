"""Tokens e chaves de teste, no formato do Supabase Auth."""

import json
import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm
from pydantic import SecretStr

from app.core.config import SupabaseSettings

USER_ID = "00000000-0000-0000-0000-00000000000a"
SUPABASE = SupabaseSettings(
    url="https://projeto.supabase.co",
    publishable_key="publica",
    secret_key=SecretStr("secreta"),
)
PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())


def make_jwks(kid: str = "k1") -> dict[str, Any]:
    key = json.loads(ECAlgorithm.to_jwk(PRIVATE_KEY.public_key()))
    return {"keys": [{**key, "kid": kid, "alg": "ES256", "use": "sig"}]}


def make_token(
    *,
    kid: str = "k1",
    key: ec.EllipticCurvePrivateKey = PRIVATE_KEY,
    remove: str | None = None,
    **overrides: Any,
) -> str:
    claims = {
        "sub": USER_ID,
        "aud": "authenticated",
        "iss": "https://projeto.supabase.co/auth/v1",
        "exp": int(time.time()) + 3600,
        **overrides,
    }
    if remove:
        del claims[remove]
    return jwt.encode(claims, key, algorithm="ES256", headers={"kid": kid})
