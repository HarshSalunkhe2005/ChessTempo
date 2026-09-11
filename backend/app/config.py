"""Environment configuration.

All secrets come from environment variables — never hardcoded, never
committed. Locally, put them in backend/.env (gitignored); on Render,
set them in the service's Environment tab.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    supabase_url: str = os.environ.get("SUPABASE_URL", "")
    # The service_role key — full DB access, bypasses Row Level Security.
    # Required because the backend acts on behalf of any user (verifying
    # their JWT itself) rather than going through Supabase's per-user auth
    # context. NEVER expose this key to the frontend.
    supabase_service_role_key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    # Used to verify the JWT Supabase issues to a logged-in frontend user.
    supabase_jwt_secret: str = os.environ.get("SUPABASE_JWT_SECRET", "")

    stockfish_path: str = os.environ.get("STOCKFISH_PATH", "stockfish")
    model_checkpoint_path: str = os.environ.get("MODEL_CHECKPOINT_PATH", "checkpoints/tempo_best.pt")
    # If set and MODEL_CHECKPOINT_PATH doesn't exist locally, downloaded
    # once at first use and cached there — e.g. a Supabase Storage public
    # URL or a signed URL to wherever the trained checkpoint actually
    # lives, since the file itself is too large to commit to git.
    model_checkpoint_url: str = os.environ.get("MODEL_CHECKPOINT_URL", "")

    # Where per-user personalization data/checkpoints live (Phase 2). Local
    # disk is enough for a single backend instance; revisit (e.g. Supabase
    # Storage) if this ever runs as more than one process.
    personalization_data_dir: str = os.environ.get("PERSONALIZATION_DATA_DIR", "data/users")
    personalization_checkpoint_dir: str = os.environ.get(
        "PERSONALIZATION_CHECKPOINT_DIR", "checkpoints/personalized"
    )

    cors_allow_origins: list[str] = os.environ.get("CORS_ALLOW_ORIGINS", "http://localhost:3000").split(",")
    # Vercel preview deployments get a fresh random subdomain per branch/PR
    # (e.g. chesstempo-git-feat-x-yourname.vercel.app) — an exact-match
    # allowlist breaks on every one of those. This regex covers your
    # production domain plus any Vercel preview URL for the project, so
    # CORS doesn't need a manual fix on every deploy.
    cors_allow_origin_regex: str = os.environ.get(
        "CORS_ALLOW_ORIGIN_REGEX", r"https://.*\.vercel\.app"
    )


settings = Settings()
