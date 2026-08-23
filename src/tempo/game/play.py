"""Ties the model, the difficulty controller, and Stockfish together to
pick the bot's actual move.

Strength blending: at low `strength`, sample straight from the model's own
move-probability distribution (human-like, error-prone). At high
`strength`, increasingly favor whatever Stockfish says is objectively best.
This gives a smooth dial instead of a hard switch between "human mode" and
"engine mode."
"""
from __future__ import annotations

import chess
import torch
import torch.nn.functional as F

from tempo.data.encoding import board_to_tensor, index_to_move
from tempo.game.engine import StockfishOracle
from tempo.mentor.difficulty import DifficultyController
from tempo.model.net import TempoNet


class TempoPlayer:
    def __init__(
        self,
        model: TempoNet,
        difficulty: DifficultyController,
        oracle: StockfishOracle | None = None,
        device: str | None = None,
    ):
        self.model = model.eval()
        self.difficulty = difficulty
        self.oracle = oracle  # optional: only needed once strength > 0
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

    @torch.no_grad()
    def _model_move_probs(self, board: chess.Board) -> torch.Tensor:
        tensor = torch.from_numpy(board_to_tensor(board)).unsqueeze(0).to(self.device)
        logits = self.model(tensor).squeeze(0)
        return F.softmax(logits, dim=0)

    def choose_move(self, board: chess.Board) -> chess.Move:
        strength = self.difficulty.strength

        # High-strength case: defer to Stockfish's top choice outright once
        # we're most of the way to "strong."
        if strength > 0.85 and self.oracle is not None:
            lines = self.oracle.best_lines(board, num_lines=1)
            if lines:
                return lines[0].move

        probs = self._model_move_probs(board)

        # Mask to only legal moves, since the raw move space includes
        # illegal from/to combinations.
        legal_moves = list(board.legal_moves)
        legal_indices = [self._move_index(m, board) for m in legal_moves]
        legal_probs = probs[legal_indices]

        if strength > 0.0 and self.oracle is not None:
            # Blend toward engine preference: reweight legal moves by how
            # close each is to Stockfish's evaluation, proportional to
            # `strength`. Simpler than re-ranking by raw eval swing, and
            # keeps the model's human-likeness at low strength.
            engine_lines = self.oracle.best_lines(board, num_lines=min(5, len(legal_moves)))
            engine_bonus = torch.zeros_like(legal_probs)
            for rank, line in enumerate(engine_lines):
                if line.move in legal_moves:
                    idx = legal_moves.index(line.move)
                    engine_bonus[idx] = 1.0 / (rank + 1)

            legal_probs = (1 - strength) * legal_probs + strength * engine_bonus

        legal_probs = legal_probs / legal_probs.sum()
        choice_idx = torch.multinomial(legal_probs, 1).item()
        return legal_moves[choice_idx]

    @staticmethod
    def _move_index(move: chess.Move, board: chess.Board) -> int:
        from tempo.data.encoding import move_to_index

        return move_to_index(move, board)
