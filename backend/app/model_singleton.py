"""Loads the trained TempoNet checkpoint once per process, and the
Stockfish oracle likewise, rather than re-loading per request.
"""
from __future__ import annotations

import logging
from pathlib import Path

import torch

from tempo.game.engine import StockfishOracle
from tempo.model.net import TempoNet

from app.config import settings

logger = logging.getLogger(__name__)

_model: TempoNet | None = None
_oracle: StockfishOracle | None = None


def get_model() -> TempoNet:
    global _model
    if _model is None:
        model = TempoNet()
        ckpt_path = Path(settings.model_checkpoint_path)
        if ckpt_path.exists():
            model.load_state_dict(torch.load(ckpt_path, map_location="cpu"))
            logger.info("Loaded model checkpoint from %s", ckpt_path)
        else:
            # No trained checkpoint yet (Phase 1 training hasn't been run/
            # deployed). Falls back to a randomly-initialized net so the
            # API stays up rather than hard-failing — moves will just be
            # nonsense until a real checkpoint is deployed.
            logger.warning(
                "No model checkpoint found at %s — serving an UNTRAINED model. "
                "Run tempo.model.train and set MODEL_CHECKPOINT_PATH.",
                ckpt_path,
            )
        model.eval()
        _model = model
    return _model


def get_oracle() -> StockfishOracle | None:
    global _oracle
    if _oracle is None:
        try:
            _oracle = StockfishOracle(path=settings.stockfish_path)
        except FileNotFoundError:
            logger.warning("Stockfish not found at %s — hints/high-difficulty play disabled.", settings.stockfish_path)
            return None
    return _oracle
