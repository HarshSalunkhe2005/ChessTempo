import chess

from tempo.mentor.motifs import (
    detect_motifs,
    find_back_rank_weakness,
    find_discovered_attack_threats,
    find_pins,
    find_skewers,
)


def test_find_pins_detects_absolute_pin():
    # Black rook on e8 pins the white bishop on e2 to the white king on e1.
    board = chess.Board("k3r3/8/8/8/8/8/4B3/4K3 w - - 0 1")
    pins = find_pins(board)
    assert len(pins) == 1
    assert pins[0].square == chess.E2


def test_find_pins_no_false_positive_when_off_the_pin_line():
    # Same pieces, but the bishop is on d3 instead of e2/e3 — off the
    # e-file the rook and king share, so nothing is actually pinned.
    board = chess.Board("k3r3/8/8/8/8/3B4/8/4K3 w - - 0 1")
    assert find_pins(board) == []


def test_find_skewers_detects_higher_value_in_front():
    # Black rook on e8 skewers the white queen on e4 into the white rook on e1.
    board = chess.Board("k3r3/8/8/8/4Q3/8/8/4R2K w - - 0 1")
    skewers = find_skewers(board)
    assert len(skewers) == 1
    assert skewers[0].square == chess.E8


def test_find_skewers_no_hit_when_front_piece_is_less_valuable():
    # Rook (front) is worth less than the queen behind it — that's a
    # "protect the queen" situation, not a skewer.
    board = chess.Board("k3r3/8/8/8/4R3/8/8/4Q2K w - - 0 1")
    assert find_skewers(board) == []


def test_find_discovered_attack_threats():
    # It's Black's move. White's own knight on e3 blocks its rook on e1
    # from attacking Black's rook on e6 — if the knight moves, Black's
    # rook is under attack.
    board = chess.Board("k7/8/4r3/8/8/4N3/8/4R2K b - - 0 1")
    threats = find_discovered_attack_threats(board)
    assert len(threats) == 1
    assert threats[0].square == chess.E3


def test_find_back_rank_weakness():
    board = chess.Board("k7/8/8/8/8/8/5PPP/6K1 w - - 0 1")
    weaknesses = find_back_rank_weakness(board)
    assert len(weaknesses) == 1
    assert weaknesses[0].square == chess.G1


def test_find_back_rank_weakness_not_flagged_when_rank_defended():
    # Same pawn shield, but a rook on the back rank covers it.
    board = chess.Board("k7/8/8/8/8/8/5PPP/4R1K1 w - - 0 1")
    assert find_back_rank_weakness(board) == []


def test_detect_motifs_runs_clean_on_start_position():
    board = chess.Board()
    assert detect_motifs(board) == []
