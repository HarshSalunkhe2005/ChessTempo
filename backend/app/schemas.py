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


class ProfileStats(BaseModel):
    total_games: int
    wins: int
    losses: int
    draws: int
    win_rate: float | None = None  # percent, None if no games yet
    current_strength: float


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
