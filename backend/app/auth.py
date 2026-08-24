"""Verify the Supabase-issued JWT sent by the frontend, so every endpoint
knows which user is making the request without trusting a client-supplied
user_id directly.
"""
from __future__ import annotations

from fastapi import Header, HTTPException
from jose import JWTError, jwt

from app.config import settings


def get_current_user_id(authorization: str = Header(...)) -> str:
    """Expects `Authorization: Bearer <supabase access token>`."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing subject")
    return user_id
