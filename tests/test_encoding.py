import chess

from tempo.data.encoding import (
    MOVE_SPACE_SIZE,
    NUM_PLANES,
    board_to_tensor,
    index_to_move,
    move_to_index,
)


def test_board_to_tensor_shape():
    board = chess.Board()
    tensor = board_to_tensor(board)
    assert tensor.shape == (NUM_PLANES, 8, 8)


def test_move_index_roundtrip_start_position():
    board = chess.Board()
    for move in board.legal_moves:
        idx = move_to_index(move, board)
        assert 0 <= idx < MOVE_SPACE_SIZE
        recovered = index_to_move(idx, board)
        assert recovered == move


def test_move_index_roundtrip_after_a_few_moves():
    board = chess.Board()
    for san in ["e4", "e5", "Nf3", "Nc6"]:
        board.push_san(san)

    for move in board.legal_moves:
        idx = move_to_index(move, board)
        recovered = index_to_move(idx, board)
        assert recovered == move


def test_promotion_move_encodes():
    board = chess.Board("8/P7/8/8/8/8/8/k1K5 w - - 0 1")
    promo_moves = [m for m in board.legal_moves if m.promotion]
    assert promo_moves, "test position should have promotion moves available"

    for move in promo_moves:
        idx = move_to_index(move, board)
        recovered = index_to_move(idx, board)
        assert recovered == move
