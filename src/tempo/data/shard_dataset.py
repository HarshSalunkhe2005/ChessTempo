"""A PyTorch Dataset that reads the sharded .npz files produced by
pgn_to_dataset.py, loading one shard into memory at a time rather than the
whole dataset — keeps this workable on a 12GB-RAM laptop."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset


class ShardedPositionDataset(Dataset):
    def __init__(self, shard_dir: Path):
        self.shard_paths = sorted(Path(shard_dir).glob("shard_*.npz"))
        if not self.shard_paths:
            raise FileNotFoundError(f"No shard_*.npz files found in {shard_dir}")

        # Index (shard_idx, offset) for every position without loading
        # every shard eagerly.
        self._lengths = []
        for p in self.shard_paths:
            with np.load(p) as data:
                self._lengths.append(len(data["moves"]))
        self._cumulative = np.cumsum(self._lengths)

        self._cached_shard_idx = None
        self._cached_boards = None
        self._cached_moves = None

    def __len__(self) -> int:
        return int(self._cumulative[-1]) if len(self._cumulative) else 0

    def _load_shard(self, shard_idx: int):
        if shard_idx != self._cached_shard_idx:
            with np.load(self.shard_paths[shard_idx]) as data:
                self._cached_boards = data["boards"]
                self._cached_moves = data["moves"]
            self._cached_shard_idx = shard_idx

    def __getitem__(self, idx: int):
        shard_idx = int(np.searchsorted(self._cumulative, idx, side="right"))
        offset = idx - (self._cumulative[shard_idx - 1] if shard_idx > 0 else 0)

        self._load_shard(shard_idx)
        board = torch.from_numpy(self._cached_boards[offset])
        move = int(self._cached_moves[offset])
        return board, move
