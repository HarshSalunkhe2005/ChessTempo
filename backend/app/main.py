"""ChessTempo API — wraps the `tempo` package (model, difficulty controller,
motif detector, Stockfish oracle) behind HTTP endpoints the frontend calls.

Run locally:
    uvicorn app.main:app --reload --port 8000
(from the backend/ directory, with the repo root's `tempo` package installed:
`pip install -e ..` from backend/, or `pip install -e .` from the repo root)
"""
from __future__ import annotations

import logging

import chess
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from tempo.mentor.difficulty import DifficultyController
from tempo.mentor.motifs import detect_motifs
from tempo.game.play import TempoPlayer

from app.auth import get_current_user_id
from app.config import settings
from app.db import get_supabase
from app.model_singleton import get_model, get_oracle
from app.schemas import (
    FinishGameRequest,
    HintResponse,
    MoveRequest,
    MoveResponse,
    ProfileResponse,
)

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="ChessTempo API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


def _get_profile(user_id: str) -> dict:
    sb = get_supabase()
    resp = sb.table("profiles").select("*").eq("id", user_id).single().execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Profile not found — did signup trigger fire?")
    return resp.data


@app.get("/profile", response_model=ProfileResponse)
def get_profile(user_id: str = Depends(get_current_user_id)):
    profile = _get_profile(user_id)
    return ProfileResponse(
        starting_difficulty=profile["starting_difficulty"],
        strength=profile["strength"],
        games_played=profile["games_played"],
        full_name=profile.get("full_name"),
    )


@app.post("/game/move", response_model=MoveResponse)
def make_move(req: MoveRequest, user_id: str = Depends(get_current_user_id)):
    """Given the current position (after the user's move), return the
    bot's reply move, chosen via the model + difficulty blend."""
    try:
        board = chess.Board(req.fen)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid FEN")

    if board.is_game_over():
        raise HTTPException(status_code=400, detail="Game is already over")

    profile = _get_profile(user_id)
    difficulty = DifficultyController(strength=profile["strength"])

    bot_color = board.turn  # the side about to move is the bot, by construction
    player = TempoPlayer(model=get_model(), difficulty=difficulty, oracle=get_oracle())
    move = player.choose_move(board)
    board.push(move)

    result = None
    if board.is_game_over():
        outcome = board.outcome()
        if outcome.winner is None:
            result = "draw"
        else:
            result = "user_loss" if outcome.winner == bot_color else "user_win"

    return MoveResponse(
        move_uci=move.uci(),
        fen_after=board.fen(),
        is_check=board.is_check(),
        is_game_over=board.is_game_over(),
        result=result,
    )


@app.post("/game/hint", response_model=HintResponse)
def get_hint(req: MoveRequest, user_id: str = Depends(get_current_user_id)):
    """Tactical motifs + eval for the current position, in human terms."""
    try:
        board = chess.Board(req.fen)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid FEN")

    motifs = detect_motifs(board)
    oracle = get_oracle()
    eval_cp = oracle.eval_cp(board) if oracle else None

    return HintResponse(
        motifs=[{"name": m.name, "square": chess.square_name(m.square), "description": m.description} for m in motifs],
        eval_cp=eval_cp,
    )


@app.post("/game/finish")
def finish_game(req: FinishGameRequest, user_id: str = Depends(get_current_user_id)):
    """Log the finished game and update the user's difficulty strength —
    the DDA update described in tempo.mentor.difficulty."""
    if req.result not in ("user_win", "user_loss", "draw"):
        raise HTTPException(status_code=400, detail="Invalid result")

    sb = get_supabase()
    profile = _get_profile(user_id)

    controller = DifficultyController(strength=profile["strength"])
    if req.result != "draw":
        controller.update_after_game(user_won=req.result == "user_win", was_close=False)

    sb.table("games").insert(
        {
            "user_id": user_id,
            "pgn": req.pgn,
            "result": req.result,
            "strength_at_start": profile["strength"],
            "strength_at_end": controller.strength,
        }
    ).execute()

    sb.table("profiles").update(
        {
            "strength": controller.strength,
            "games_played": profile["games_played"] + 1,
        }
    ).eq("id", user_id).execute()

    return {"new_strength": controller.strength}
