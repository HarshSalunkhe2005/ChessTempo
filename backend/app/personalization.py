"""Wires tempo.mentor.personalization (game logging + fine-tune cadence)
into the backend. Called as a FastAPI background task after each finished
game — see app.main.finish_game — so it never adds latency to the
request that reports a game result.

Uses the local filesystem for shards/checkpoints, matching
app.model_singleton's expectations (one backend process serving from one
disk). Revisit if this ever needs to run as more than one instance.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import chess

from tempo.mentor.personalization import (
    is_finetune_due,
    log_game_for_personalization,
    run_personalization_finetune,
)

from app.config import settings
from app.db import get_supabase

logger = logging.getLogger(__name__)

# The user always plays White against the bot (the frontend always makes
# the human move first — see ChessGame.tsx's onDrop/requestBotReply flow),
# the same assumption app.main.make_move relies on for `bot_color`.
USER_COLOR = chess.WHITE


def handle_finished_game(user_id: str, pgn: str, games_played: int) -> None:
    shard_dir = Path(settings.personalization_data_dir) / user_id / "shards"
    log_game_for_personalization(pgn, USER_COLOR, shard_dir)

    sb = get_supabase()
    resp = sb.table("personalization_state").select("*").eq("user_id", user_id).single().execute()
    state = resp.data
    if state is None:
        logger.warning("No personalization_state row for user %s — skipping fine-tune check", user_id)
        return

    if not is_finetune_due(games_played, state["games_at_last_finetune"]):
        return

    base_checkpoint = Path(settings.model_checkpoint_path)
    if not base_checkpoint.exists():
        logger.info("No base checkpoint yet — skipping personalization fine-tune for user %s", user_id)
        return

    out_path = Path(settings.personalization_checkpoint_dir) / f"{user_id}.pt"
    try:
        ran = run_personalization_finetune(base_checkpoint, shard_dir, out_path)
    except Exception:
        # A background fine-tune job failing (bad data, OOM, etc.) should
        # never take the request path down with it — log and move on; the
        # user just keeps playing against their last-known-good model.
        logger.exception("Personalization fine-tune failed for user %s", user_id)
        return

    if not ran:
        return

    sb.table("personalization_state").update(
        {
            "last_finetuned_at": datetime.now(timezone.utc).isoformat(),
            "games_at_last_finetune": games_played,
            "model_checkpoint_path": str(out_path),
        }
    ).eq("user_id", user_id).execute()
    logger.info("Personalized model updated for user %s -> %s", user_id, out_path)
