from tempo.mentor.insights import (
    average_moves,
    compute_streaks,
    identify_opening,
    move_count,
    summarize_openings,
)

RUY = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 *"
ITALIAN = "1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 *"
SICILIAN = "1. e4 c5 2. Nf3 d6 *"
NIMZO = "1. d4 Nf6 2. c4 e6 3. Nc3 Bb4 *"  # 3...Bb4 gives check — marks must be ignored
ODD = "1. a3 e5 *"


def test_identify_opening_picks_most_specific_line():
    assert identify_opening(RUY) == "Ruy Lopez"
    assert identify_opening(ITALIAN) == "Italian Game"
    assert identify_opening(SICILIAN) == "Sicilian Defense"


def test_identify_opening_ignores_check_symbols():
    assert identify_opening(NIMZO) == "Nimzo-Indian Defense"


def test_identify_opening_falls_back_by_first_move():
    assert identify_opening("1. e4 h6 *") == "King's Pawn Game"
    assert identify_opening("1. d4 h6 *") == "Queen's Pawn Game"
    assert identify_opening(ODD) == "Other opening"
    assert identify_opening("") == "Unknown"


def test_move_count_rounds_up_partial_move():
    assert move_count("1. e4 e5 2. Nf3 *") == 2
    assert move_count("1. e4 e5 2. Nf3 Nc6 *") == 2


def test_streaks():
    empty = compute_streaks([])
    assert (empty.current_result, empty.current_length, empty.best_win_streak) == (None, 0, 0)

    s = compute_streaks(["user_loss", "user_win", "user_win", "user_win", "user_loss", "user_loss"])
    assert s.current_result == "user_loss"
    assert s.current_length == 2
    assert s.best_win_streak == 3


def test_summarize_openings_counts_results_and_sorts():
    games = [
        (RUY, "user_win"),
        (RUY, "user_loss"),
        (RUY, "draw"),
        (SICILIAN, "user_win"),
    ]
    stats = summarize_openings(games)
    assert stats[0].name == "Ruy Lopez"
    assert (stats[0].games, stats[0].wins, stats[0].draws, stats[0].losses) == (3, 1, 1, 1)
    assert stats[1].name == "Sicilian Defense"


def test_average_moves():
    assert average_moves([]) is None
    assert average_moves(["1. e4 e5 *", "1. e4 e5 2. Nf3 Nc6 *"]) == 1.5
