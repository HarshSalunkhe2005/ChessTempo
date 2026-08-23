"""Turn a filtered PGN file into (position, move) training pairs, saved as
sharded .npz files (small enough for a 4GB-VRAM laptop to load in chunks
rather than needing everything in RAM at once).

Usage:
    python -m tempo.data.pgn_to_dataset data/lichess_2024-01_r1200-1800.pgn
"""
from __future__ import annotations

import argparse
from pathlib import Path

import chess
import chess.pgn
import numpy as np
from tqdm import tqdm

from tempo.data.encoding import board_to_tensor, move_to_index

SHARD_SIZE = 200_000  # positions per .npz shard


def games_to_shards(pgn_path: Path, out_dir: Path, shard_size: int = SHARD_SIZE) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    boards_buf: list[np.ndarray] = []
    moves_buf: list[int] = []
    shard_idx = 0

    def flush():
        nonlocal shard_idx, boards_buf, moves_buf
        if not boards_buf:
            return
        out_path = out_dir / f"shard_{shard_idx:04d}.npz"
        np.savez_compressed(
            out_path,
            boards=np.stack(boards_buf),
            moves=np.array(moves_buf, dtype=np.int64),
        )
        print(f"Wrote {out_path} ({len(boards_buf)} positions)")
        shard_idx += 1
        boards_buf, moves_buf = [], []

    with open(pgn_path, encoding="utf-8", errors="replace") as fh:
        pbar = tqdm(desc="games")
        while True:
            game = chess.pgn.read_game(fh)
            if game is None:
                break
            pbar.update(1)

            board = game.board()
            for move in game.mainline_moves():
                boards_buf.append(board_to_tensor(board))
                moves_buf.append(move_to_index(move, board))
                board.push(move)

                if len(boards_buf) >= shard_size:
                    flush()

    flush()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pgn_path", type=Path)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--shard-size", type=int, default=SHARD_SIZE)
    args = parser.parse_args()

    out_dir = args.out_dir or args.pgn_path.parent / (args.pgn_path.stem + "_shards")
    games_to_shards(args.pgn_path, out_dir, args.shard_size)


if __name__ == "__main__":
    main()
