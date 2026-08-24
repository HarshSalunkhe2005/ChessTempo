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
