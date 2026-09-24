"""Aggregate stats derived from a user's finished games — streaks, which
openings they actually reach, typical game length — for the profile page.

All pure functions over (pgn, result) history; nothing here touches the
database or the engine, so it's cheap to run per request and easy to test.
"""
from __future__ import annotations

import io
import math
from collections import defaultdict
from dataclasses import dataclass

import chess
import chess.pgn

# Longest-prefix match against the SAN move sequence both sides played.
# A small hand-picked table of openings people actually run into, not a
# full ECO database — anything unmatched falls back to a coarse label
# based on White's first move, so every game lands somewhere honest.
_OPENINGS: list[tuple[str, str]] = [
    ("Ruy Lopez", "e4 e5 Nf3 Nc6 Bb5"),
    ("Italian Game", "e4 e5 Nf3 Nc6 Bc4"),
    ("Scotch Game", "e4 e5 Nf3 Nc6 d4"),
    ("Petrov's Defense", "e4 e5 Nf3 Nf6"),
    ("King's Gambit", "e4 e5 f4"),
    ("Vienna Game", "e4 e5 Nc3"),
    ("Sicilian Defense", "e4 c5"),
    ("French Defense", "e4 e6"),
    ("Caro-Kann Defense", "e4 c6"),
    ("Scandinavian Defense", "e4 d5"),
    ("Pirc Defense", "e4 d6"),
    ("Modern Defense", "e4 g6"),
    ("Alekhine's Defense", "e4 Nf6"),
    ("Open Game", "e4 e5"),
    ("Queen's Gambit Declined", "d4 d5 c4 e6"),
    ("Slav Defense", "d4 d5 c4 c6"),
    ("Queen's Gambit Accepted", "d4 d5 c4 dxc4"),
    ("Queen's Gambit", "d4 d5 c4"),
    ("London System", "d4 d5 Bf4"),
    ("Nimzo-Indian Defense", "d4 Nf6 c4 e6 Nc3 Bb4"),
    ("Queen's Indian Defense", "d4 Nf6 c4 e6 Nf3 b6"),
    ("King's Indian Defense", "d4 Nf6 c4 g6"),
    ("Indian Defense", "d4 Nf6"),
    ("Dutch Defense", "d4 f5"),
    ("English Opening", "c4"),
    ("Réti Opening", "Nf3 d5 c4"),
    ("Zukertort Opening", "Nf3"),
    ("Bird's Opening", "f4"),
]

_FIRST_MOVE_FALLBACK = {
    "e4": "King's Pawn Game",
    "d4": "Queen's Pawn Game",
}
_MAX_PLIES_CONSIDERED = 12


def _strip_marks(san: str) -> str:
    return san.rstrip("+#")


def _opening_table() -> list[tuple[str, list[str]]]:
    table = [(name, seq.split()) for name, seq in _OPENINGS]
    # Longest sequence first so the most specific line wins.
    table.sort(key=lambda item: len(item[1]), reverse=True)
    return table


_TABLE = _opening_table()


def _san_moves(pgn: str, max_plies: int = _MAX_PLIES_CONSIDERED) -> list[str]:
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        return []
    board = game.board()
    sans: list[str] = []
    for move in game.mainline_moves():
        sans.append(_strip_marks(board.san(move)))
        board.push(move)
        if len(sans) >= max_plies:
            break
    return sans


def identify_opening(pgn: str) -> str:
    sans = _san_moves(pgn)
    if not sans:
        return "Unknown"
    for name, seq in _TABLE:
        if sans[: len(seq)] == seq:
            return name
    return _FIRST_MOVE_FALLBACK.get(sans[0], "Other opening")


def move_count(pgn: str) -> int:
    """Full moves the game lasted (a game ending after White's 3rd move
    counts as 3)."""
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        return 0
    plies = sum(1 for _ in game.mainline_moves())
    return math.ceil(plies / 2)


@dataclass
class Streaks:
    current_result: str | None  # result type of the most recent run, None if no games
    current_length: int
    best_win_streak: int


def compute_streaks(results_chronological: list[str]) -> Streaks:
    if not results_chronological:
        return Streaks(current_result=None, current_length=0, best_win_streak=0)

    best = run = 0
    for r in results_chronological:
        run = run + 1 if r == "user_win" else 0
        best = max(best, run)

    latest = results_chronological[-1]
    length = 0
    for r in reversed(results_chronological):
        if r != latest:
            break
        length += 1
    return Streaks(current_result=latest, current_length=length, best_win_streak=best)


@dataclass
class OpeningStat:
    name: str
    games: int
    wins: int
    draws: int
    losses: int


def summarize_openings(games: list[tuple[str, str]], top_n: int = 5) -> list[OpeningStat]:
    """`games` is [(pgn, result)]; returns the most-played openings with
    how the user actually scored in each."""
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"user_win": 0, "draw": 0, "user_loss": 0})
    for pgn, result in games:
        name = identify_opening(pgn)
        if result in buckets[name]:
            buckets[name][result] += 1

    stats = [
        OpeningStat(
            name=name,
            games=sum(counts.values()),
            wins=counts["user_win"],
            draws=counts["draw"],
            losses=counts["user_loss"],
        )
        for name, counts in buckets.items()
    ]
    stats.sort(key=lambda s: (-s.games, s.name))
    return stats[:top_n]


def average_moves(pgns: list[str]) -> float | None:
    counts = [move_count(p) for p in pgns]
    counts = [c for c in counts if c > 0]
    if not counts:
        return None
    return round(sum(counts) / len(counts), 1)
