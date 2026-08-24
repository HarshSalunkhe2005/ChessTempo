"""Verify the Supabase-issued JWT sent by the frontend, so every endpoint
knows which user is making the request without trusting a client-supplied
user_id directly.

Newer Supabase projects sign tokens with an asymmetric key (ES256) rather
than the legacy shared HS256 secret, and publish the public key via a
JWKS endpoint. We verify against that JWKS, with the old shared-secret
path kept as a fallback for projects still on the legacy scheme.
"""
from __future__ import annotations

import logging
import time

import requests
from fastapi import Header, HTTPException
from jose import jwk, jwt
from jose.exceptions import JOSEError
from jose.utils import base64url_decode

from app.config import settings

logger = logging.getLogger(__name__)

_jwks_cache: dict | None = None
_jwks_cache_at: float = 0
_JWKS_TTL_SECONDS = 3600


def _get_jwks() -> dict:
    global _jwks_cache, _jwks_cache_at
    if _jwks_cache is None or (time.time() - _jwks_cache_at) > _JWKS_TTL_SECONDS:
        resp = requests.get(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json", timeout=5)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_cache_at = time.time()
    return _jwks_cache


def _verify_with_jwks(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")

    jwks = _get_jwks()
    matching = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if matching is None:
        # Key rotated since our cache was populated — refetch once before giving up.
        global _jwks_cache
        _jwks_cache = None
        jwks = _get_jwks()
        matching = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)

    if matching is None:
        raise HTTPException(status_code=401, detail="Invalid token: unknown signing key")

    key = jwk.construct(matching, matching.get("alg", "ES256"))
    message, encoded_sig = token.rsplit(".", 1)
    decoded_sig = base64url_decode(encoded_sig.encode())
    if not key.verify(message.encode(), decoded_sig):
        raise HTTPException(status_code=401, detail="Invalid token: signature verification failed")

    return jwt.get_unverified_claims(token)


def get_current_user_id(authorization: str = Header(...)) -> str:
    """Expects `Authorization: Bearer <supabase access token>`."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()

    try:
        header = jwt.get_unverified_header(token)
    except JOSEError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    try:
        if header.get("alg") == "HS256" and settings.supabase_jwt_secret:
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        else:
            payload = _verify_with_jwks(token)
    except HTTPException:
        raise
    except JOSEError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    except requests.RequestException as e:
        logger.error("Failed to fetch Supabase JWKS: %s", e)
        raise HTTPException(status_code=503, detail="Could not verify token — auth service unreachable")

    if payload.get("aud") != "authenticated":
        raise HTTPException(status_code=401, detail="Invalid token: wrong audience")

    exp = payload.get("exp")
    if exp is not None and exp < time.time():
        raise HTTPException(status_code=401, detail="Invalid token: expired")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing subject")
    return user_id
