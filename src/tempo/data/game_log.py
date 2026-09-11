"""Phase 2: turn one finished game into personalization training data.

Unlike `pgn_to_dataset.py` (which encodes *every* move in a bulk archive
for base-model training), personalization only wants the moves the human
actually played — the goal is predicting *their* patterns, not the bot's
own replies to them.
"""
from __future__ import annotations

import io
import uuid
from pathlib import Path

import chess
import chess.pgn
import numpy as np

from tempo.data.encoding import NUM_PLANES, board_to_tensor, move_to_index

_EMPTY_BOARDS = np.empty((0, NUM_PLANES, 8, 8), dtype=np.float32)
_EMPTY_MOVES = np.empty((0,), dtype=np.int64)


def game_to_user_positions(pgn: str, user_color: chess.Color) -> tuple[np.ndarray, np.ndarray]:
    """(board_tensor, move_index) pairs for just `user_color`'s moves in a
    finished game."""
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        return _EMPTY_BOARDS, _EMPTY_MOVES

    board = game.board()
    boards, moves = [], []
    for move in game.mainline_moves():
        if board.turn == user_color:
            boards.append(board_to_tensor(board))
            moves.append(move_to_index(move, board))
        board.push(move)

    if not boards:
        return _EMPTY_BOARDS, _EMPTY_MOVES
    return np.stack(boards), np.array(moves, dtype=np.int64)


def append_game_shard(pgn: str, user_color: chess.Color, shard_dir: Path) -> Path | None:
    """Write one small shard for a single finished game into `shard_dir`,
    in the same .npz format `tempo.data.shard_dataset.ShardedPositionDataset`
    already reads — just one game's worth per file instead of the bulk
    pipeline's SHARD_SIZE positions. Returns None (writes nothing) if the
    user didn't make any moves worth logging (e.g. they resigned on move 1).
    """
    boards, moves = game_to_user_positions(pgn, user_color)
    if len(moves) == 0:
        return None

    shard_dir.mkdir(parents=True, exist_ok=True)
    out_path = shard_dir / f"shard_{uuid.uuid4().hex}.npz"
    np.savez_compressed(out_path, boards=boards, moves=moves)
    return out_path
