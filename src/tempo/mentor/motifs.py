"""Phase 4: rule-based tactical motif detection.

Explaining *why* a move matters in human terms is far more reliable done
this way than by asking a language model to reason about a position — this
pattern-matches concrete tactics against python-chess board state.

Starts with the highest-value, easiest-to-detect motifs. Extend this list
over time rather than trying to cover every tactic on day one.

Every detector here is framed the same way: "what should the side to move
(board.turn) watch out for right now" — hanging pieces of ours, forks
against us, our own pins, skewers against us, discovered-attack threats
from the opponent, and weaknesses in our own king position. That framing
keeps the motif list consistent regardless of which side calls the hint
endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass

import chess


@dataclass
class Motif:
    name: str
    square: int  # the square the motif centers on, for UI highlighting
    description: str


PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,  # never actually compared against — the king is never "captured"
}

_ROOK_DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
_BISHOP_DIRECTIONS = [(1, 1), (1, -1), (-1, 1), (-1, -1)]


def _slider_directions(piece_type: chess.PieceType) -> list[tuple[int, int]]:
    directions = []
    if piece_type in (chess.ROOK, chess.QUEEN):
        directions += _ROOK_DIRECTIONS
    if piece_type in (chess.BISHOP, chess.QUEEN):
        directions += _BISHOP_DIRECTIONS
    return directions


def _ray_squares(square: int, direction: tuple[int, int]) -> list[int]:
    """Squares along a ray from `square` in `direction`, nearest first,
    stopping at the board edge."""
    file, rank = chess.square_file(square), chess.square_rank(square)
    df, dr = direction
    squares = []
    f, r = file + df, rank + dr
    while 0 <= f < 8 and 0 <= r < 8:
        squares.append(chess.square(f, r))
        f, r = f + df, r + dr
    return squares


def _first_two_occupants(board: chess.Board, square: int, direction: tuple[int, int]):
    """The first two occupied squares (nearest first) along a ray from
    `square`, as (square, piece) pairs. May return fewer than 2 entries."""
    occupants = []
    for sq in _ray_squares(square, direction):
        piece = board.piece_at(sq)
        if piece is not None:
            occupants.append((sq, piece))
            if len(occupants) == 2:
                break
    return occupants


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


def find_pins(board: chess.Board) -> list[Motif]:
    """A pinned piece can't (legally) move without exposing our own king
    to check — python-chess already tracks this for us."""
    motifs = []
    for square, piece in board.piece_map().items():
        if piece.color != board.turn or piece.piece_type == chess.KING:
            continue
        if board.is_pinned(board.turn, square):
            motifs.append(
                Motif(
                    name="pin",
                    square=square,
                    description=f"Your {chess.piece_name(piece.piece_type)} on "
                    f"{chess.square_name(square)} is pinned to your king — moving it "
                    "may expose your king to check.",
                )
            )
    return motifs


def find_skewers(board: chess.Board) -> list[Motif]:
    """A skewer: an opponent sliding piece attacks through one of our
    pieces onto a second, less valuable one of ours behind it — the front
    piece has to move (it's the more valuable one), exposing the piece
    behind it to capture."""
    motifs = []
    us, them = board.turn, not board.turn

    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None or piece.color != them:
            continue

        for direction in _slider_directions(piece.piece_type):
            occupants = _first_two_occupants(board, square, direction)
            if len(occupants) < 2:
                continue
            (front_sq, front_piece), (back_sq, back_piece) = occupants
            if front_piece.color != us or back_piece.color != us:
                continue
            if PIECE_VALUES[front_piece.piece_type] > PIECE_VALUES[back_piece.piece_type]:
                motifs.append(
                    Motif(
                        name="skewer",
                        square=square,
                        description=f"Opponent's {chess.piece_name(piece.piece_type)} on "
                        f"{chess.square_name(square)} skewers your {chess.piece_name(front_piece.piece_type)} "
                        f"on {chess.square_name(front_sq)} into your {chess.piece_name(back_piece.piece_type)} "
                        f"on {chess.square_name(back_sq)}.",
                    )
                )
    return motifs


def find_discovered_attack_threats(board: chess.Board) -> list[Motif]:
    """One of the opponent's own pieces is sitting between one of their
    sliding pieces and one of ours — if they move that blocker, the
    sliding piece attacks us. A heuristic, not a full search: it doesn't
    check whether the blocker is actually free to move (e.g. pinned in
    place itself), just that the geometry is there."""
    motifs = []
    us, them = board.turn, not board.turn

    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None or piece.color != them:
            continue

        for direction in _slider_directions(piece.piece_type):
            occupants = _first_two_occupants(board, square, direction)
            if len(occupants) < 2:
                continue
            (blocker_sq, blocker), (target_sq, target) = occupants
            if blocker.color != them or target.color != us or target.piece_type == chess.PAWN:
                continue
            motifs.append(
                Motif(
                    name="discovered_attack_threat",
                    square=blocker_sq,
                    description=f"If the opponent's {chess.piece_name(blocker.piece_type)} on "
                    f"{chess.square_name(blocker_sq)} moves, their {chess.piece_name(piece.piece_type)} on "
                    f"{chess.square_name(square)} would attack your {chess.piece_name(target.piece_type)} "
                    f"on {chess.square_name(target_sq)}.",
                )
            )
    return motifs


def find_back_rank_weakness(board: chess.Board) -> list[Motif]:
    """Our king is stuck on its home back rank behind its own pawn shield,
    with no rook/queen of ours still defending that rank — the classic
    setup for a back-rank mate."""
    us = board.turn
    king_square = board.king(us)
    if king_square is None:
        return []

    back_rank = 0 if us == chess.WHITE else 7
    if chess.square_rank(king_square) != back_rank:
        return []

    push_rank = 1 if us == chess.WHITE else 6
    king_file = chess.square_file(king_square)
    escape_files = [f for f in (king_file - 1, king_file, king_file + 1) if 0 <= f < 8]

    blocked = all(
        (blocker := board.piece_at(chess.square(f, push_rank))) is not None and blocker.color == us
        for f in escape_files
    )
    if not blocked:
        return []

    back_rank_squares = [chess.square(f, back_rank) for f in range(8)]
    has_defender = any(
        (p := board.piece_at(sq)) is not None and p.color == us and p.piece_type in (chess.ROOK, chess.QUEEN)
        for sq in back_rank_squares
    )
    if has_defender:
        return []

    return [
        Motif(
            name="back_rank_weakness",
            square=king_square,
            description="Your king is boxed in on the back rank behind its own pawns, with "
            "nothing defending that rank — watch out for back-rank mate threats.",
        )
    ]


def detect_motifs(board: chess.Board) -> list[Motif]:
    """Run all detectors and return whatever's found, most concrete first."""
    return (
        find_hanging_pieces(board)
        + find_forks(board)
        + find_pins(board)
        + find_skewers(board)
        + find_discovered_attack_threats(board)
        + find_back_rank_weakness(board)
    )
