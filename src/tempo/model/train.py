"""Base-model training loop: predict the human move from a position.

Usage:
    python -m tempo.model.train data/lichess_2024-01_r1200-1800_shards --epochs 5
"""
from __future__ import annotations

import argparse
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Subset, random_split
from tqdm import tqdm

from tempo.data.shard_dataset import ShardedPositionDataset, ShardShuffleSampler
from tempo.model.net import TempoNet


def train(
    shard_dir: Path,
    epochs: int = 5,
    batch_size: int = 256,
    lr: float = 1e-3,
    val_fraction: float = 0.02,
    val_shards: int = 1,
    checkpoint_dir: Path = Path("checkpoints"),
    device: str | None = None,
) -> None:
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on {device}")

    dataset = ShardedPositionDataset(shard_dir)
    num_shards = len(dataset.shard_paths)

    if num_shards <= val_shards:
        # Not enough shards to hold any out entirely (including the
        # trivial single-shard case) — fall back to a random within-shard
        # split. No thrashing risk here: with this few shards, everything
        # ends up cached almost immediately regardless of access order.
        val_size = max(1, int(len(dataset) * val_fraction))
        train_size = len(dataset) - val_size
        train_ds, val_ds = random_split(dataset, [train_size, val_size])
        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
        val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)
    else:
        # Hold out `val_shards` whole shards — i.e. entirely unseen games,
        # not just unseen positions from games the model already trained
        # on some positions of — and shuffle the rest via
        # ShardShuffleSampler so training still gets SGD's usual shuffling
        # benefit without re-reading a shard file per sample (see that
        # class's docstring for why a plain global shuffle is much slower
        # here, not just less correct).
        train_shard_ids = list(range(num_shards - val_shards))
        val_shard_ids = list(range(num_shards - val_shards, num_shards))
        ranges = dataset.shard_index_ranges()

        train_sampler = ShardShuffleSampler(dataset, train_shard_ids)
        val_indices = [i for sid in val_shard_ids for i in range(*ranges[sid])]
        val_ds = Subset(dataset, val_indices)

        train_loader = DataLoader(dataset, batch_size=batch_size, sampler=train_sampler, num_workers=0)
        val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)
        train_size = len(train_sampler)

    model = TempoNet().to(device)
    print(f"Model parameters: {model.num_parameters():,}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()

    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    best_val_acc = 0.0

    for epoch in range(1, epochs + 1):
        model.train()
        running_loss = 0.0
        for boards, moves in tqdm(train_loader, desc=f"epoch {epoch} [train]"):
            boards, moves = boards.to(device), moves.to(device)

            optimizer.zero_grad()
            logits = model(boards)
            loss = criterion(logits, moves)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * boards.size(0)

        train_loss = running_loss / train_size

        model.eval()
        correct, total = 0, 0
        with torch.no_grad():
            for boards, moves in tqdm(val_loader, desc=f"epoch {epoch} [val]"):
                boards, moves = boards.to(device), moves.to(device)
                logits = model(boards)
                preds = logits.argmax(dim=1)
                correct += (preds == moves).sum().item()
                total += moves.size(0)

        val_acc = correct / total if total else 0.0
        print(f"Epoch {epoch}: train_loss={train_loss:.4f} val_move_match_acc={val_acc:.4f}")

        ckpt_path = checkpoint_dir / f"tempo_epoch{epoch}.pt"
        torch.save(model.state_dict(), ckpt_path)

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), checkpoint_dir / "tempo_best.pt")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("shard_dir", type=Path)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument(
        "--val-shards", type=int, default=1, help="Whole shards to hold out for validation"
    )
    parser.add_argument("--checkpoint-dir", type=Path, default=Path("checkpoints"))
    args = parser.parse_args()

    train(
        args.shard_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        val_shards=args.val_shards,
        checkpoint_dir=args.checkpoint_dir,
    )


if __name__ == "__main__":
    main()
