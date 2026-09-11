import numpy as np

from tempo.data.encoding import NUM_PLANES
from tempo.data.shard_dataset import ShardedPositionDataset, ShardShuffleSampler


def _write_shard(shard_dir, name: str, n: int, move_offset: int) -> None:
    boards = np.zeros((n, NUM_PLANES, 8, 8), dtype=np.float32)
    moves = np.arange(move_offset, move_offset + n, dtype=np.int64)
    np.savez_compressed(shard_dir / name, boards=boards, moves=moves)


def test_shard_index_ranges(tmp_path):
    _write_shard(tmp_path, "shard_0000.npz", 5, 0)
    _write_shard(tmp_path, "shard_0001.npz", 3, 100)
    dataset = ShardedPositionDataset(tmp_path)

    assert dataset.shard_index_ranges() == [(0, 5), (5, 8)]
    assert len(dataset) == 8


def test_shard_shuffle_sampler_visits_every_index_once(tmp_path):
    _write_shard(tmp_path, "shard_0000.npz", 5, 0)
    _write_shard(tmp_path, "shard_0001.npz", 7, 100)
    _write_shard(tmp_path, "shard_0002.npz", 4, 200)
    dataset = ShardedPositionDataset(tmp_path)

    sampler = ShardShuffleSampler(dataset, shard_ids=[0, 1, 2])
    indices = list(sampler)

    assert len(sampler) == len(dataset) == 16
    assert sorted(indices) == list(range(16))


def test_shard_shuffle_sampler_only_visits_requested_shards(tmp_path):
    _write_shard(tmp_path, "shard_0000.npz", 5, 0)
    _write_shard(tmp_path, "shard_0001.npz", 7, 100)
    dataset = ShardedPositionDataset(tmp_path)

    # Only shard 1 (global indices 5..11)
    sampler = ShardShuffleSampler(dataset, shard_ids=[1])
    indices = sorted(sampler)

    assert indices == list(range(5, 12))


def test_shard_shuffle_sampler_never_reloads_a_shard_mid_epoch(tmp_path, monkeypatch):
    # The whole point of ShardShuffleSampler: consecutive indices from the
    # sampler should only ever require loading each shard once, not
    # bouncing back and forth between shards.
    _write_shard(tmp_path, "shard_0000.npz", 50, 0)
    _write_shard(tmp_path, "shard_0001.npz", 50, 100)
    _write_shard(tmp_path, "shard_0002.npz", 50, 200)
    dataset = ShardedPositionDataset(tmp_path)

    load_calls = []
    original_load = ShardedPositionDataset._load_shard

    def counting_load(self, shard_idx):
        load_calls.append(shard_idx)
        return original_load(self, shard_idx)

    monkeypatch.setattr(ShardedPositionDataset, "_load_shard", counting_load)

    sampler = ShardShuffleSampler(dataset, shard_ids=[0, 1, 2])
    for idx in sampler:
        dataset[idx]

    # _load_shard is called on every __getitem__, but it should only
    # actually *change* shard (a cache miss) 3 times total (once per
    # shard), never bouncing back to a shard already finished.
    distinct_transitions = [load_calls[0]] + [
        b for a, b in zip(load_calls, load_calls[1:]) if a != b
    ]
    assert len(distinct_transitions) == 3
