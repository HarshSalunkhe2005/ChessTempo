"""A PyTorch Dataset that reads the sharded .npz files produced by
pgn_to_dataset.py, loading one shard into memory at a time rather than the
whole dataset — keeps this workable on a 12GB-RAM laptop."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator, Sequence

import numpy as np
import torch
from torch.utils.data import Dataset, Sampler


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

    def shard_index_ranges(self) -> list[tuple[int, int]]:
        """[(start, end), ...] global index ranges for each shard, in the
        same order as `shard_paths`."""
        ranges = []
        prev = 0
        for c in self._cumulative:
            ranges.append((prev, int(c)))
            prev = int(c)
        return ranges


class ShardShuffleSampler(Sampler[int]):
    """Shuffles *within* each shard and shuffles shard visitation order,
    but never interleaves shards — each shard gets loaded (and decoded)
    at most once per epoch instead of on nearly every `__getitem__` call.

    A plain `DataLoader(..., shuffle=True)` draws a fresh random global
    index for every single sample; with more than a couple of shards, that
    almost always misses `ShardedPositionDataset`'s one-shard cache, so
    every sample re-reads and re-decompresses a whole shard file from
    disk. Concretely: on a 10-shard dataset this turned a should-be-fast
    training step into ~30 seconds per batch. Restricting shuffling to
    "shard order + within-shard order" keeps SGD's shuffling benefit
    without that thrashing.
    """

    def __init__(self, dataset: ShardedPositionDataset, shard_ids: Sequence[int], generator=None):
        self.dataset = dataset
        self.shard_ids = list(shard_ids)
        self.generator = generator

    def __iter__(self) -> Iterator[int]:
        ranges = self.dataset.shard_index_ranges()
        shard_order = torch.randperm(len(self.shard_ids), generator=self.generator).tolist()
        for pos in shard_order:
            start, end = ranges[self.shard_ids[pos]]
            local_order = torch.randperm(end - start, generator=self.generator).tolist()
            for offset in local_order:
                yield start + offset

    def __len__(self) -> int:
        ranges = self.dataset.shard_index_ranges()
        return sum(ranges[sid][1] - ranges[sid][0] for sid in self.shard_ids)
