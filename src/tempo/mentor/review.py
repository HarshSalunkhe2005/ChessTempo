"""Post-game move-quality review: classify every move in a finished game
against Stockfish, the same broad idea used by every serious chess site
(lichess's move annotations, chess.com's Game Review) — nobody owns the
underlying technique, "how much worse than the engine's best move was
this," even if the exact label set and thresholds differ site to site.

This is compute-heavy (one Stockfish call per half-move) — see the
performance note on `review_game` before wiring it into a slow request
path.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import chess
import chess.engine
import chess.pgn
import io

from tempo.game.engine import StockfishOracle
from tempo.mentor.motifs import find_hanging_pieces

# Half-moves treated as "Book" without an engine call, purely to save
# compute — not a real opening book lookup. A real one (Polyglot or
# similar) is a reasonable follow-up.
BOOK_PLY_COUNT = 6

# Centipawn-loss thresholds, mover's-perspective. Ordered worst-first so
# the first match wins.
_THRESHOLDS = [
    (200, "Blunder"),
    (90, "Mistake"),
    (40, "Inaccuracy"),
    (10, "Good"),
]


@dataclass
class MoveReview:
    ply: int
    san: str
    color: str  # "white" | "black"
    classification: str
    eval_cp: int | None  # position eval after the move, from White's perspective


def _classify(cp_loss: int, is_best: bool, is_brilliant: bool) -> str:
    if is_brilliant:
        return "Brilliant"
    if is_best:
        return "Best"
    for threshold, label in _THRESHOLDS:
        if cp_loss >= threshold:
            return label
    return "Excellent"


def _looks_brilliant(board_after: chess.Board, moved_to: int, mover_color: bool, cp_loss: int) -> bool:
    """Rough heuristic for chess.com-style 'Brilliant': the move was
    (near-)best AND leaves the just-moved piece looking like a sacrifice
    (attacked, undefended) while still being sound. Real brilliancy
    detection also checks the sacrifice was actually necessary/only-move
    — this is a simplification, not a claim of parity with any site's
    exact algorithm.
    """
    if cp_loss > 10:
        return False
    piece = board_after.piece_at(moved_to)
    if piece is None or piece.piece_type == chess.PAWN:
        return False
    attackers = board_after.attackers(not mover_color, moved_to)
    defenders = board_after.attackers(mover_color, moved_to)
    return bool(attackers) and not defenders


def review_game(pgn: str, oracle: StockfishOracle, depth: int | None = None) -> tuple[list[MoveReview], dict]:
    """Walk a finished game move by move, scoring each against Stockfish.

    Performance note: this makes ~2 engine calls per half-move (eval +
    best-line) at whatever depth `oracle` is configured for. A 40-move
    game is ~160 engine calls — on Render's free tier this can take
    tens of seconds and risks the request timing out. Fine for now;
    revisit as a background job (store the result, poll for it) once
    real usage shows it's a problem rather than guessing upfront.
    """
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        return [], {"white": None, "black": None}

    board = game.board()
    reviews: list[MoveReview] = []
    cp_losses = {"white": [], "black": []}

    for ply, move in enumerate(game.mainline_moves(), start=1):
        mover_color = board.turn
        color_name = "white" if mover_color == chess.WHITE else "black"
        san = board.san(move)

        if ply <= BOOK_PLY_COUNT:
            board.push(move)
            reviews.append(MoveReview(ply=ply, san=san, color=color_name, classification="Book", eval_cp=None))
            continue

        best_lines = oracle.best_lines(board, num_lines=1)
        best_move = best_lines[0].move if best_lines else None
        best_eval = best_lines[0].score_cp if best_lines else 0

        is_best = move == best_move
        board.push(move)

        eval_after_mover_pov = -oracle.eval_cp(board)  # turn flipped after push
        cp_loss = max(0, (best_eval or 0) - eval_after_mover_pov)
        cp_losses[color_name].append(cp_loss)

        brilliant = _looks_brilliant(board, move.to_square, mover_color, cp_loss)
        classification = _classify(cp_loss, is_best, brilliant)

        eval_white_pov = eval_after_mover_pov if mover_color == chess.WHITE else -eval_after_mover_pov
        reviews.append(
            MoveReview(ply=ply, san=san, color=color_name, classification=classification, eval_cp=eval_white_pov)
        )

    accuracy = {
        "white": _accuracy_from_losses(cp_losses["white"]),
        "black": _accuracy_from_losses(cp_losses["black"]),
    }
    return reviews, accuracy


def estimate_game_closeness(
    pgn: str, user_color: chess.Color, oracle: StockfishOracle, threshold_cp: int = 150
) -> bool:
    """Rough proxy for "was this game close," fed into
    `tempo.mentor.difficulty.DifficultyController.update_after_game` so a
    narrow finish doesn't swing strength as hard as a rout.

    Evaluates the position right before the final move (always legal/
    non-terminal, unlike the actual final position, which may be
    checkmate) from the user's perspective — a small eval swing there
    means the user was still in the fight almost to the end.
    """
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        return False

    moves = list(game.mainline_moves())
    if len(moves) < 2:
        return False

    board = game.board()
    for move in moves[:-1]:
        board.push(move)

    try:
        eval_cp = oracle.eval_cp(board)
    except (chess.engine.EngineError, OSError):
        return False

    eval_user_pov = eval_cp if board.turn == user_color else -eval_cp
    return abs(eval_user_pov) < threshold_cp


def _accuracy_from_losses(losses: list[int]) -> float | None:
    """A published approximation of the win%-based accuracy formula used
    by major chess sites (average centipawn loss -> a 0-100 accuracy
    score via a decaying exponential) — not any single site's exact
    proprietary formula, just the same well-known shape."""
    if not losses:
        return None
    avg = sum(losses) / len(losses)
    accuracy = 103.1668 * math.exp(-0.04354 * avg) - 3.1669
    return round(max(0.0, min(100.0, accuracy)), 1)
