"""Phase 2: decide when a user's personalized model is due for a re-tune,
and run that fine-tune. Kept separate from `tempo.model.finetune` (the
training loop itself) so the "when" policy can change independently.
"""
from __future__ import annotations

from pathlib import Path

import chess

from tempo.data.game_log import append_game_shard
from tempo.model.finetune import finetune

# Re-tune every N games played against the bot since the last fine-tune —
# frequent enough to feel responsive to a user's recent games, infrequent
# enough that each run has more than a handful of new positions to learn
# from. Revisit once real usage shows whether this cadence feels right
# (see docs/PLAN.md's open questions).
GAMES_PER_FINETUNE = 10


def games_until_next_finetune(games_played: int, games_at_last_finetune: int) -> int:
    return max(0, GAMES_PER_FINETUNE - (games_played - games_at_last_finetune))


def is_finetune_due(games_played: int, games_at_last_finetune: int) -> bool:
    return games_until_next_finetune(games_played, games_at_last_finetune) == 0


def log_game_for_personalization(pgn: str, user_color: chess.Color, user_shard_dir: Path) -> None:
    """Called after every finished game, regardless of whether a fine-tune
    is due yet — keeps building up the user's shard history so it's ready
    once it is."""
    append_game_shard(pgn, user_color, user_shard_dir)


def run_personalization_finetune(base_checkpoint: Path, user_shard_dir: Path, out_path: Path) -> bool:
    """Fine-tune the base model on everything logged for this user so far.
    Returns False (no-op) if there's nothing to train on yet."""
    if not any(user_shard_dir.glob("shard_*.npz")):
        return False
    finetune(base_checkpoint, user_shard_dir, out_path)
    return True
