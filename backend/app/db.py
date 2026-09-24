"""Supabase client, using the service_role key — the backend acts as a
trusted server, verifying user identity itself via JWT (see auth.py)
rather than relying on Supabase's client-side RLS context.
"""
from __future__ import annotations

from postgrest.exceptions import APIError
from supabase import Client, create_client

from app.config import settings

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set (see backend/.env.example)"
            )
        _client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return _client


def single_or_none(query) -> dict | None:
    """Run a `.single()` query, returning None when no row matches.

    The real client *raises* (PostgREST PGRST116) on zero rows rather than
    returning empty data, so a plain `if not resp.data` check never fires —
    a valid token for a deleted account got a 500 instead of a 404.
    """
    try:
        return query.execute().data
    except APIError as e:
        if e.code == "PGRST116":
            return None
        raise
