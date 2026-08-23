"""Phase 4: rule-based tactical motif detection.

Explaining *why* a move matters in human terms is far more reliable done
this way than by asking a language model to reason about a position — this
pattern-matches concrete tactics against python-chess board state.

Starts with the highest-value, easiest-to-detect motifs. Extend this list
over time rather than trying to cover every tactic on day one.
"""
from __future__ import annotations

from dataclasses import dataclass

import chess


@dataclass
class Motif:
    name: str
    square: int  # the square the motif centers on, for UI highlighting
    description: str


def find_hanging_pieces(board: chess.Board) -> list[Motif]:
    """A piece is 'hanging' if it's attacked by the opponent and not
    defended by anyone on our side."""
    motifs = []
    for square, piece in board.piece_map().items():
        if piece.color != board.turn:
            continue
        attackers = board.attackers(not board.turn, square)
        defenders = board.attackers(board.turn, square)
        if attackers and not defenders:
            motifs.append(
                Motif(
                    name="hanging_piece",
                    square=square,
                    description=f"Your {chess.piece_name(piece.piece_type)} on "
                    f"{chess.square_name(square)} is undefended and under attack.",
                )
            )
    return motifs


def find_forks(board: chess.Board) -> list[Motif]:
    """A simple fork check: does any opponent piece attack 2+ of our
    pieces worth more than a pawn from a single square?"""
    motifs = []
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None or piece.color == board.turn:
            continue
        attacked = [
            t
            for t in board.attacks(square)
            if (target := board.piece_at(t)) and target.color == board.turn and target.piece_type != chess.PAWN
        ]
        if len(attacked) >= 2:
            targets = ", ".join(chess.square_name(t) for t in attacked)
            motifs.append(
                Motif(
                    name="fork",
                    square=square,
                    description=f"Opponent's {chess.piece_name(piece.piece_type)} on "
                    f"{chess.square_name(square)} forks your pieces on {targets}.",
                )
            )
    return motifs


def detect_motifs(board: chess.Board) -> list[Motif]:
    """Run all detectors and return whatever's found, most concrete first."""
    return find_hanging_pieces(board) + find_forks(board)
