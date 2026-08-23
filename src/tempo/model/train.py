"""Base-model training loop: predict the human move from a position.

Usage:
    python -m tempo.model.train data/lichess_2024-01_r1200-1800_shards --epochs 5
"""
from __future__ import annotations

import argparse
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split
from tqdm import tqdm

from tempo.data.shard_dataset import ShardedPositionDataset
from tempo.model.net import TempoNet


def train(
    shard_dir: Path,
    epochs: int = 5,
    batch_size: int = 256,
    lr: float = 1e-3,
    val_fraction: float = 0.02,
    checkpoint_dir: Path = Path("checkpoints"),
    device: str | None = None,
) -> None:
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on {device}")

    dataset = ShardedPositionDataset(shard_dir)
    val_size = max(1, int(len(dataset) * val_fraction))
    train_size = len(dataset) - val_size
    train_ds, val_ds = random_split(dataset, [train_size, val_size])

    # num_workers=0 avoids re-opening every shard file per worker process,
    # which thrashes on a laptop; the shard cache in ShardedPositionDataset
    # already keeps sequential access cheap.
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)

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
    parser.add_argument("--checkpoint-dir", type=Path, default=Path("checkpoints"))
    args = parser.parse_args()

    train(
        args.shard_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        checkpoint_dir=args.checkpoint_dir,
    )


if __name__ == "__main__":
    main()
