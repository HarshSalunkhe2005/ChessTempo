"""Phase 2: personalize a base model to one user's own games.

This is the same training loop as model/train.py, but starting from a
pretrained checkpoint, on a much smaller per-user dataset, for few epochs
and a low learning rate — a light nudge, not retraining from scratch. This
mirrors the approach in the Maia follow-up work ("Learning Personalized
Models of Human Behavior in Chess"): fine-tune the general human-move model
on an individual's games rather than training a new one per person.

Usage:
    python -m tempo.model.finetune checkpoints/tempo_best.pt data/user123_shards --epochs 2
"""
from __future__ import annotations

import argparse
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from tqdm import tqdm

from tempo.data.shard_dataset import ShardedPositionDataset, ShardShuffleSampler
from tempo.model.net import TempoNet


def finetune(
    base_checkpoint: Path,
    user_shard_dir: Path,
    out_path: Path,
    epochs: int = 2,
    batch_size: int = 64,
    lr: float = 1e-4,
    device: str | None = None,
) -> None:
    """Fine-tune `base_checkpoint` on one user's games, saving the result
    to `out_path`. Intended to be re-run periodically (e.g. every N new
    games) as more of the user's history accumulates.
    """
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")

    model = TempoNet().to(device)
    model.load_state_dict(torch.load(base_checkpoint, map_location=device))

    dataset = ShardedPositionDataset(user_shard_dir)
    # Per-user shards accumulate one-per-game (tempo.data.game_log) and can
    # number in the dozens — a plain shuffle=True thrashes
    # ShardedPositionDataset's one-shard cache the same way it does for
    # bulk training (see ShardShuffleSampler's docstring), just with
    # smaller, faster-to-reload shards. Still worth avoiding.
    sampler = ShardShuffleSampler(dataset, shard_ids=range(len(dataset.shard_paths)))
    loader = DataLoader(dataset, batch_size=batch_size, sampler=sampler, num_workers=0)

    # Small LR + few epochs: we want the model nudged toward this user's
    # tendencies, not overwritten by a tiny dataset.
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()

    model.train()
    for epoch in range(1, epochs + 1):
        running_loss = 0.0
        for boards, moves in tqdm(loader, desc=f"finetune epoch {epoch}"):
            boards, moves = boards.to(device), moves.to(device)

            optimizer.zero_grad()
            logits = model(boards)
            loss = criterion(logits, moves)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * boards.size(0)

        print(f"Epoch {epoch}: loss={running_loss / len(dataset):.4f}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out_path)
    print(f"Saved personalized model to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_checkpoint", type=Path)
    parser.add_argument("user_shard_dir", type=Path)
    parser.add_argument("--out", type=Path, default=Path("checkpoints/personalized.pt"))
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-4)
    args = parser.parse_args()

    finetune(
        args.base_checkpoint,
        args.user_shard_dir,
        args.out,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
    )


if __name__ == "__main__":
    main()
