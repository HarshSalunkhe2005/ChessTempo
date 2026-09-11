import chess

from tempo.data.game_log import append_game_shard, game_to_user_positions
from tempo.data.shard_dataset import ShardedPositionDataset
from tempo.mentor.personalization import games_until_next_finetune, is_finetune_due

SAMPLE_PGN = """[Event "Casual game"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0
"""


def test_game_to_user_positions_only_includes_that_color():
    boards, moves = game_to_user_positions(SAMPLE_PGN, chess.WHITE)
    # White played 3 moves: e4, Nf3, Bb5
    assert len(moves) == 3
    assert boards.shape[0] == 3

    boards_b, moves_b = game_to_user_positions(SAMPLE_PGN, chess.BLACK)
    # Black played 3 moves: e5, Nc6, a6
    assert len(moves_b) == 3


def test_game_to_user_positions_empty_for_no_moves():
    boards, moves = game_to_user_positions("[Result \"*\"]\n\n*\n", chess.WHITE)
    assert len(moves) == 0
    assert boards.shape[0] == 0


def test_append_game_shard_round_trips_through_dataset(tmp_path):
    out_path = append_game_shard(SAMPLE_PGN, chess.WHITE, tmp_path)
    assert out_path is not None
    assert out_path.exists()

    dataset = ShardedPositionDataset(tmp_path)
    assert len(dataset) == 3


def test_append_game_shard_returns_none_for_empty_game(tmp_path):
    out_path = append_game_shard("[Result \"*\"]\n\n*\n", chess.WHITE, tmp_path)
    assert out_path is None
    assert list(tmp_path.glob("shard_*.npz")) == []


def test_finetune_cadence():
    assert not is_finetune_due(games_played=5, games_at_last_finetune=0)
    assert is_finetune_due(games_played=10, games_at_last_finetune=0)
    assert is_finetune_due(games_played=25, games_at_last_finetune=10)
    assert games_until_next_finetune(games_played=7, games_at_last_finetune=0) == 3
