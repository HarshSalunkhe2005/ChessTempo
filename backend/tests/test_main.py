"""Integration tests for app.main, against a fake Supabase client
(fake_supabase.py) so nothing here needs a real Supabase project,
Stockfish binary, or trained checkpoint.
"""
from __future__ import annotations

import chess
import pytest
from fastapi.testclient import TestClient

from app import main
from app.auth import get_current_user_id
from tests.fake_supabase import FakeSupabase

USER_ID = "11111111-1111-1111-1111-111111111111"


def _profile(**overrides) -> dict:
    base = {
        "id": USER_ID,
        "full_name": "Test User",
        "starting_difficulty": "casual",
        "strength": 0.30,
        "games_played": 3,
    }
    base.update(overrides)
    return base


@pytest.fixture
def fake_db(monkeypatch):
    fake = FakeSupabase(
        data={
            "profiles": [_profile()],
            "personalization_state": [{"user_id": USER_ID, "games_at_last_finetune": 0}],
        }
    )
    monkeypatch.setattr(main, "get_supabase", lambda: fake)
    return fake


@pytest.fixture
def client(fake_db):
    main.app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def test_health_needs_no_auth():
    resp = TestClient(main.app).get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_get_profile(client, fake_db):
    resp = client.get("/profile")
    assert resp.status_code == 200
    body = resp.json()
    assert body["starting_difficulty"] == "casual"
    assert body["games_played"] == 3


def test_get_profile_404_when_missing(client, fake_db):
    fake_db.data["profiles"] = []
    resp = client.get("/profile")
    assert resp.status_code == 404


def test_hint_hides_eval_number_for_beginner(client, fake_db, monkeypatch):
    fake_db.data["profiles"][0]["strength"] = 0.1  # beginner tier

    monkeypatch.setattr(main, "get_oracle", lambda: _FakeOracle(eval_cp=250))

    # White to move with an undefended knight on d4 (attacked by the e5
    # pawn) — a hanging-piece motif for White to watch out for, so this
    # also exercises the "capped to one motif" behavior below.
    board = chess.Board("4k3/8/8/4p3/3N4/8/8/4K3 w - - 0 1")
    resp = client.post("/game/hint", json={"fen": board.fen()})
    assert resp.status_code == 200
    body = resp.json()
    assert body["eval_cp"] is None
    assert body["eval_label"] == "Slightly better"
    assert len(body["motifs"]) <= 1


def test_hint_shows_eval_number_for_strong_player(client, fake_db, monkeypatch):
    fake_db.data["profiles"][0]["strength"] = 0.9  # strong tier

    monkeypatch.setattr(main, "get_oracle", lambda: _FakeOracle(eval_cp=250))

    board = chess.Board("4k3/8/8/4p3/3N4/8/8/4K3 w - - 0 1")
    resp = client.post("/game/hint", json={"fen": board.fen()})
    assert resp.status_code == 200
    body = resp.json()
    assert body["eval_cp"] == 250
    assert body["eval_label"] is None


def test_finish_game_records_result_and_updates_strength(client, fake_db, monkeypatch):
    # No oracle -> closeness defaults to False, keeping this deterministic.
    monkeypatch.setattr(main, "get_oracle", lambda: None)
    scheduled = {}
    monkeypatch.setattr(
        main, "handle_finished_game", lambda user_id, pgn, games_played: scheduled.update(
            user_id=user_id, pgn=pgn, games_played=games_played
        )
    )

    pgn = "[Result \"1-0\"]\n\n1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0\n"
    resp = client.post("/game/finish", json={"pgn": pgn, "result": "user_win"})
    assert resp.status_code == 200

    new_strength = resp.json()["new_strength"]
    assert new_strength > 0.30  # a win should nudge strength up

    inserted = [c for c in fake_db.calls if c[0] == "insert" and c[1] == "games"]
    assert len(inserted) == 1
    assert inserted[0][2]["result"] == "user_win"

    updated = [c for c in fake_db.calls if c[0] == "update" and c[1] == "profiles"]
    assert len(updated) == 1
    assert updated[0][2]["games_played"] == 4

    # The background task is scheduled with the post-increment games count.
    assert scheduled == {"user_id": USER_ID, "pgn": pgn, "games_played": 4}


def test_finish_game_rejects_invalid_result(client, fake_db):
    resp = client.post("/game/finish", json={"pgn": "1. e4 *", "result": "not_a_result"})
    assert resp.status_code == 400


class _FakeOracle:
    def __init__(self, eval_cp: int):
        self._eval_cp = eval_cp

    def eval_cp(self, board):
        return self._eval_cp
