"""Loads TempoNet checkpoints and the Stockfish oracle once per process
rather than per request.

Caches one model per checkpoint path (the shared base model, plus one per
user once they have a personalized checkpoint — see
tempo.mentor.personalization), keyed by path and invalidated automatically
when the file's mtime changes, so a freshly fine-tuned checkpoint gets
picked up on the next request without restarting the process.
"""
from __future__ import annotations

import logging
from pathlib import Path

import requests
import torch

from tempo.game.engine import StockfishOracle
from tempo.model.net import TempoNet

from app.config import settings

logger = logging.getLogger(__name__)

# Belt-and-suspenders alongside the OMP/MKL env vars set in app.main
# (which must land before torch's C extension initializes) — this model
# is small enough that single-threaded CPU inference costs nothing
# noticeable in latency, while multi-threaded defaults cost real memory
# on a constrained instance.
torch.set_num_threads(1)

_model_cache: dict[str, TempoNet] = {}
_model_mtime: dict[str, float] = {}
_oracle: StockfishOracle | None = None


def _download_checkpoint(url: str, dest: Path) -> None:
    logger.info("Downloading model checkpoint from %s", url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(resp.content)
    tmp.replace(dest)


def _base_checkpoint_path() -> Path:
    path = Path(settings.model_checkpoint_path)
    if not path.exists() and settings.model_checkpoint_url:
        try:
            _download_checkpoint(settings.model_checkpoint_url, path)
        except requests.RequestException:
            logger.exception("Failed to download model checkpoint from %s", settings.model_checkpoint_url)
    return path


def _load_from_cache_or_disk(cache_key: str, ckpt_path: Path) -> TempoNet:
    mtime = ckpt_path.stat().st_mtime if ckpt_path.exists() else None
    cached = _model_cache.get(cache_key)
    if cached is not None and _model_mtime.get(cache_key) == mtime:
        return cached

    model = TempoNet()
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
    _model_cache[cache_key] = model
    _model_mtime[cache_key] = mtime
    return model


def get_model(user_id: str | None = None) -> TempoNet:
    """The base model, or a user's personalized fine-tune once one exists
    on disk at `<personalization_checkpoint_dir>/<user_id>.pt`."""
    if user_id:
        personalized_path = Path(settings.personalization_checkpoint_dir) / f"{user_id}.pt"
        if personalized_path.exists():
            return _load_from_cache_or_disk(str(personalized_path), personalized_path)

    base_path = _base_checkpoint_path()
    return _load_from_cache_or_disk(str(base_path), base_path)


def evict_user_model(user_id: str) -> None:
    """Drop a deleted user's cached personalized model from memory."""
    key = str(Path(settings.personalization_checkpoint_dir) / f"{user_id}.pt")
    _model_cache.pop(key, None)
    _model_mtime.pop(key, None)


def get_oracle() -> StockfishOracle | None:
    global _oracle
    if _oracle is None:
        try:
            _oracle = StockfishOracle(path=settings.stockfish_path)
        except FileNotFoundError:
            logger.warning("Stockfish not found at %s — hints/high-difficulty play disabled.", settings.stockfish_path)
            return None
    return _oracle
