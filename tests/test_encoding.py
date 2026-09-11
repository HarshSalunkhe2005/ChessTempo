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


def test_underpromotion_from_different_source_squares_does_not_collide():
    # Two pawns (b7, d7) can both capture onto c8 and underpromote there —
    # a from-square-blind encoding would map both dxc8=N and bxc8=N to the
    # same index, making one of them unreachable.
    board = chess.Board("2r1r3/1PbPb3/8/8/8/8/8/k1K5 w - - 0 1")
    underpromo_moves = [
        m for m in board.legal_moves if m.promotion and m.promotion != chess.QUEEN
    ]
    assert len(underpromo_moves) >= 6, "expected multiple pawns able to underpromote onto c8"

    indices = [move_to_index(m, board) for m in underpromo_moves]
    assert len(indices) == len(set(indices)), "underpromotion moves must map to distinct indices"

    for move in underpromo_moves:
        idx = move_to_index(move, board)
        assert index_to_move(idx, board) == move


def test_en_passant_square_is_encoded():
    board = chess.Board()
    for san in ["e4", "a6", "e5", "d5"]:
        board.push_san(san)
    assert board.ep_square is not None, "test setup should leave an en-passant target square"

    tensor = board_to_tensor(board)
    ep_plane = tensor[17]
    assert ep_plane.sum() == 1.0, "exactly one square should be marked as the en-passant target"

    board_without_ep = chess.Board()
    for san in ["e4", "a6", "Nf3", "Nf6"]:
        board_without_ep.push_san(san)
    assert board_to_tensor(board_without_ep)[17].sum() == 0.0
