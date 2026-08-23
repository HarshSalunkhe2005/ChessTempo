"""A small CNN policy network: board planes in, a probability distribution
over the move space out.

Deliberately small (kept in the tens-of-thousands to low-millions of
parameters) — this is meant to predict the move a human would play, not to
out-search a strong engine, so it doesn't need AlphaZero-scale depth. Sized
to comfortably fit a 4GB-VRAM GPU with a reasonable batch size.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from tempo.data.encoding import MOVE_SPACE_SIZE, NUM_PLANES


class ResidualBlock(nn.Module):
    def __init__(self, channels: int):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(channels)
        self.conv2 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        return F.relu(out + residual)


class TempoNet(nn.Module):
    """~6 residual blocks at 64 channels — comparable in spirit to the
    small end of Maia's architecture, not to a full AlphaZero net."""

    def __init__(self, channels: int = 64, num_blocks: int = 6):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(NUM_PLANES, channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
        )
        self.blocks = nn.Sequential(*[ResidualBlock(channels) for _ in range(num_blocks)])

        self.policy_head = nn.Sequential(
            nn.Conv2d(channels, 32, 1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Flatten(),
            nn.Linear(32 * 8 * 8, MOVE_SPACE_SIZE),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.stem(x)
        x = self.blocks(x)
        return self.policy_head(x)  # raw logits over MOVE_SPACE_SIZE

    def num_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters())
