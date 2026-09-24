from __future__ import annotations

from pydantic import BaseModel


class MoveRequest(BaseModel):
    fen: str  # current board position


class MoveResponse(BaseModel):
    move_uci: str
    fen_after: str
    is_check: bool
    is_game_over: bool
    result: str | None = None  # "user_win" | "user_loss" | "draw" | None


class HintResponse(BaseModel):
    motifs: list[dict]
    eval_cp: int | None = None
    eval_label: str | None = None


class FinishGameRequest(BaseModel):
    pgn: str
    result: str  # "user_win" | "user_loss" | "draw"


class ProfileResponse(BaseModel):
    starting_difficulty: str
    strength: float
    games_played: int
    full_name: str | None = None


class GameSummary(BaseModel):
    id: str
    result: str
    strength_at_start: float
    strength_at_end: float
    created_at: str
    pgn: str


class ProfileStats(BaseModel):
    total_games: int
    wins: int
    losses: int
    draws: int
    win_rate: float | None = None  # percent, None if no games yet
    current_strength: float


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    starting_difficulty: str | None = None  # resets strength to that tier's starting value


class OpeningStatOut(BaseModel):
    name: str
    games: int
    wins: int
    draws: int
    losses: int


class StreakInfo(BaseModel):
    current_result: str | None = None  # "user_win" | "user_loss" | "draw" | None
    current_length: int = 0
    best_win_streak: int = 0


class PersonalizationInfo(BaseModel):
    last_finetuned_at: str | None = None
    games_until_next_tune: int
    # False after a backend restart on ephemeral disk even if a tune ran
    # earlier — the DB row remembers, the checkpoint file may not.
    model_active: bool


class ProfileInsights(BaseModel):
    streak: StreakInfo
    avg_moves_per_game: float | None = None
    openings: list[OpeningStatOut]
    personalization: PersonalizationInfo


class ReviewRequest(BaseModel):
    pgn: str


class MoveReviewOut(BaseModel):
    ply: int
    san: str
    color: str
    classification: str
    eval_cp: int | None = None


class ReviewResponse(BaseModel):
    moves: list[MoveReviewOut]
    accuracy_white: float | None = None
    accuracy_black: float | None = None
