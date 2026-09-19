"""Thin wrapper around Stockfish (via UCI) for ground-truth evaluation.

Stockfish is used only as an oracle — for hints and for scoring how
"close"/blunder-y a game was for the difficulty controller — never as the
thing playing the bot's own moves. That's the model's job (tempo.model).
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass

import chess
import chess.engine


@dataclass
class EngineLine:
    move: chess.Move
    score_cp: int | None  # centipawns from the side-to-move's perspective; None if mate
    mate_in: int | None


class StockfishOracle:
    def __init__(self, path: str | None = None, depth: int = 14):
        path = path or shutil.which("stockfish")
        if not path:
            raise FileNotFoundError(
                "Stockfish binary not found on PATH. Install it and/or pass `path=` explicitly."
            )
        self.depth = depth
        self._engine = chess.engine.SimpleEngine.popen_uci(path)
        # Explicit and small rather than relying on Stockfish's own
        # default — this runs alongside a full PyTorch process on
        # memory-constrained deployments (e.g. Render's free 512MB plan),
        # and the oracle only ever needs single-line/eval-depth analysis,
        # not a large transposition table.
        self._engine.configure({"Hash": 16, "Threads": 1})

    def best_lines(self, board: chess.Board, num_lines: int = 3) -> list[EngineLine]:
        infos = self._engine.analyse(board, chess.engine.Limit(depth=self.depth), multipv=num_lines)
        if isinstance(infos, dict):
            infos = [infos]

        lines = []
        for info in infos:
            pv = info.get("pv")
            if not pv:
                continue
            score = info["score"].pov(board.turn)
            lines.append(
                EngineLine(
                    move=pv[0],
                    score_cp=score.score(mate_score=100000),
                    mate_in=score.mate(),
                )
            )
        return lines

    def eval_cp(self, board: chess.Board) -> int:
        """Single-number eval in centipawns, from the side-to-move's view."""
        info = self._engine.analyse(board, chess.engine.Limit(depth=self.depth))
        return info["score"].pov(board.turn).score(mate_score=100000)

    def close(self) -> None:
        self._engine.quit()

    def __enter__(self) -> "StockfishOracle":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
