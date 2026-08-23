"""Board <-> tensor encoding, and move <-> index encoding.

The model sees a position as a stack of 8x8 binary planes (like AlphaZero /
Maia, simplified) and outputs a probability over a fixed-size move space,
similar to the "policy head" approach used by those engines.
"""
from __future__ import annotations

import chess
import numpy as np

PIECE_TYPES = [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING]

# 6 piece types x 2 colors = 12 "is this piece here" planes, plus 6 metadata
# planes (side to move, castling rights x4, en-passant-ish placeholder).
NUM_PLANES = 12 + 6
BOARD_SIZE = 8


def board_to_tensor(board: chess.Board) -> np.ndarray:
    """Encode a python-chess Board as a (NUM_PLANES, 8, 8) float32 array.

    Always encoded from the perspective of the side to move (board is
    mirrored for Black), which halves the effective input space the model
    has to learn.
    """
    planes = np.zeros((NUM_PLANES, BOARD_SIZE, BOARD_SIZE), dtype=np.float32)
    flip = board.turn == chess.BLACK

    for square, piece in board.piece_map().items():
        row, col = divmod(square, 8)
        if flip:
            row, col = 7 - row, 7 - col
        plane_idx = PIECE_TYPES.index(piece.piece_type)
        if piece.color != board.turn:
            plane_idx += 6
        planes[plane_idx, row, col] = 1.0

    meta_base = 12
    planes[meta_base, :, :] = 1.0  # side-to-move plane (always "us" after flip)
    planes[meta_base + 1, :, :] = float(board.has_kingside_castling_rights(board.turn))
    planes[meta_base + 2, :, :] = float(board.has_queenside_castling_rights(board.turn))
    planes[meta_base + 3, :, :] = float(board.has_kingside_castling_rights(not board.turn))
    planes[meta_base + 4, :, :] = float(board.has_queenside_castling_rights(not board.turn))
    planes[meta_base + 5, :, :] = float(board.is_check())

    return planes


def _square_to_flipped(square: int, flip: bool) -> int:
    if not flip:
        return square
    row, col = divmod(square, 8)
    return (7 - row) * 8 + (7 - col)


# Move space: from_square (64) x to_square (64) = 4096, plus underpromotion
# variants (knight/bishop/rook; queen promotion is covered by the plain
# from/to pair) for the 3 forward-diagonal-ish promotion squares per side.
# This mirrors AlphaZero's "from-to plus underpromotion flag" trick, kept
# simple rather than the full 73-plane move encoding.
NUM_UNDERPROMOTIONS = 3  # knight, bishop, rook
MOVE_SPACE_SIZE = 64 * 64 + 64 * NUM_UNDERPROMOTIONS

_UNDERPROMO_PIECES = [chess.KNIGHT, chess.BISHOP, chess.ROOK]


def move_to_index(move: chess.Move, board: chess.Board) -> int:
    """Map a legal move (from the mover's perspective, board-flip aware) to
    a fixed index in [0, MOVE_SPACE_SIZE)."""
    flip = board.turn == chess.BLACK
    frm = _square_to_flipped(move.from_square, flip)
    to = _square_to_flipped(move.to_square, flip)

    if move.promotion and move.promotion != chess.QUEEN:
        promo_idx = _UNDERPROMO_PIECES.index(move.promotion)
        return 64 * 64 + to * NUM_UNDERPROMOTIONS + promo_idx

    return frm * 64 + to


def index_to_move(index: int, board: chess.Board) -> chess.Move | None:
    """Inverse of move_to_index, resolved against legal moves on `board` so
    castling/en-passant/queen-promotion notation comes out correct."""
    flip = board.turn == chess.BLACK

    for legal in board.legal_moves:
        if move_to_index(legal, board) == index:
            return legal
    return None
