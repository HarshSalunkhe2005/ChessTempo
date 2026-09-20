"""ChessTempo API — wraps the `tempo` package (model, difficulty controller,
motif detector, Stockfish oracle) behind HTTP endpoints the frontend calls.

Run locally:
    uvicorn app.main:app --reload --port 8000
(from the backend/ directory, with the repo root's `tempo` package installed:
`pip install -e ..` from backend/, or `pip install -e .` from the repo root)
"""
from __future__ import annotations

import logging
import os

# Must be set before torch (imported transitively below, via
# tempo.game.play -> tempo.model.net) initializes its CPU backend.
# PyTorch's default thread pool sizes itself to the host's *reported*
# CPU count, which on a memory-constrained free-tier instance (e.g.
# Render's free plan: 512MB RAM) can allocate enough per-thread buffer
# overhead on top of everything else running (Stockfish, FastAPI, the
# checkpoint itself) to get OOM-killed on the very first inference —
# observed for real on this project's Render deployment. Pinning to a
# single thread is the standard fix for PyTorch-in-a-small-container.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import chess
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from tempo.mentor.difficulty import DifficultyController
from tempo.mentor.hints import build_hint_payload
from tempo.mentor.motifs import detect_motifs
from tempo.mentor.review import estimate_game_closeness, review_game
from tempo.game.play import TempoPlayer

from app.auth import get_current_user_id
from app.config import settings
from app.db import get_supabase
from app.model_singleton import get_model, get_oracle
from app.personalization import USER_COLOR, handle_finished_game
from app.schemas import (
    FinishGameRequest,
    GameSummary,
    HintResponse,
    MoveRequest,
    MoveResponse,
    MoveReviewOut,
    ProfileResponse,
    ProfileStats,
    ReviewRequest,
    ReviewResponse,
)

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="ChessTempo API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_origin_regex=settings.cors_allow_origin_regex,
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
    player = TempoPlayer(model=get_model(user_id), difficulty=difficulty, oracle=get_oracle())
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
    """Tactical motifs + eval for the current position, in human terms —
    scaled to the user's current skill estimate (tempo.mentor.hints)."""
    try:
        board = chess.Board(req.fen)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid FEN")

    profile = _get_profile(user_id)
    motifs = detect_motifs(board)
    oracle = get_oracle()
    eval_cp = oracle.eval_cp(board) if oracle else None

    payload = build_hint_payload(motifs, eval_cp, profile["strength"])
    return HintResponse(
        motifs=[
            {"name": m.name, "square": chess.square_name(m.square), "description": m.description}
            for m in payload.motifs
        ],
        eval_cp=payload.eval_cp,
        eval_label=payload.eval_label,
    )


@app.post("/game/finish")
def finish_game(req: FinishGameRequest, background_tasks: BackgroundTasks, user_id: str = Depends(get_current_user_id)):
    """Log the finished game, update the user's difficulty strength (the
    DDA update described in tempo.mentor.difficulty), and kick off
    personalization bookkeeping (tempo.mentor.personalization) in the
    background so this request doesn't wait on it."""
    if req.result not in ("user_win", "user_loss", "draw"):
        raise HTTPException(status_code=400, detail="Invalid result")

    sb = get_supabase()
    profile = _get_profile(user_id)

    oracle = get_oracle()
    was_close = (
        estimate_game_closeness(req.pgn, USER_COLOR, oracle) if oracle is not None else False
    )

    controller = DifficultyController(strength=profile["strength"])
    if req.result != "draw":
        controller.update_after_game(user_won=req.result == "user_win", was_close=was_close)

    sb.table("games").insert(
        {
            "user_id": user_id,
            "pgn": req.pgn,
            "result": req.result,
            "strength_at_start": profile["strength"],
            "strength_at_end": controller.strength,
        }
    ).execute()

    games_played = profile["games_played"] + 1
    sb.table("profiles").update(
        {
            "strength": controller.strength,
            "games_played": games_played,
        }
    ).eq("id", user_id).execute()

    background_tasks.add_task(handle_finished_game, user_id, req.pgn, games_played)

    return {"new_strength": controller.strength}


@app.get("/games", response_model=list[GameSummary])
def list_games(user_id: str = Depends(get_current_user_id), limit: int = 20):
    """Recent game history for the profile page."""
    sb = get_supabase()
    resp = (
        sb.table("games")
        .select("id, result, strength_at_start, strength_at_end, created_at, pgn")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [GameSummary(**row) for row in resp.data]


@app.get("/profile/stats", response_model=ProfileStats)
def get_profile_stats(user_id: str = Depends(get_current_user_id)):
    """Aggregate win/loss/draw record for the profile page."""
    sb = get_supabase()
    profile = _get_profile(user_id)
    resp = sb.table("games").select("result").eq("user_id", user_id).execute()

    wins = sum(1 for g in resp.data if g["result"] == "user_win")
    losses = sum(1 for g in resp.data if g["result"] == "user_loss")
    draws = sum(1 for g in resp.data if g["result"] == "draw")
    total = len(resp.data)

    return ProfileStats(
        total_games=total,
        wins=wins,
        losses=losses,
        draws=draws,
        win_rate=round(100 * wins / total, 1) if total else None,
        current_strength=profile["strength"],
    )


@app.post("/game/review", response_model=ReviewResponse)
def review(req: ReviewRequest, user_id: str = Depends(get_current_user_id)):
    """Move-by-move quality classification for a finished game (Best,
    Good, Inaccuracy, Mistake, Blunder, occasionally Brilliant) plus a
    per-side accuracy percentage — see tempo.mentor.review for the method
    and its honest limitations (heuristic, not any site's exact formula).

    Slow: one to two Stockfish calls per half-move. Fine for now; a
    background-job version is the right fix if this becomes a real
    bottleneck under actual usage.
    """
    oracle = get_oracle()
    if oracle is None:
        raise HTTPException(status_code=503, detail="Stockfish unavailable — can't review this game right now")

    moves, accuracy = review_game(req.pgn, oracle)
    return ReviewResponse(
        moves=[MoveReviewOut(**vars(m)) for m in moves],
        accuracy_white=accuracy["white"],
        accuracy_black=accuracy["black"],
    )
