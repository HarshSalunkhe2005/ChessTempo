# Tempo

A chess helper that grows with you instead of a fixed-ELO bot.

Most training bots either play at full strength or a hand-capped "weakened"
version of a strong engine (fewer search plies, added randomness). Tempo
instead:

1. Learns to play like a **human**, not an engine — trained on real games,
   predicting the move a person would make rather than the objectively best
   one (à la [Maia Chess](https://github.com/CSSLab/maia-chess)).
2. **Personalizes** to you specifically — fine-tuning on your own games as
   you play, so it starts predicting (and eventually countering) your
   patterns.
3. **Auto-adjusts difficulty** during play instead of using a fixed rating,
   based on how the games are actually going.
4. Gives **hints in human terms** ("watch your knight," not just an eval
   number), scaled to your current skill estimate.

## How it's built

```
Lichess game archives ──► data pipeline ──► base model (plays "human-like")
                                                   │
                                     fine-tune on your own games
                                                   │
                                          your personal model
                                                   │
                      ┌────────────────────────────┴───────────────────────┐
                      │                                                    │
              move selection (bot's move)                     hint engine (what it tells you)
                      │                                                    │
            difficulty controller (adjusts strength)      motif detector (fork/pin/hanging piece)
```

- **`src/tempo/data/`** — downloading and parsing Lichess PGN archives into
  (position, move) training pairs.
- **`src/tempo/model/`** — the board-to-move-probability network and
  training/fine-tuning scripts.
- **`src/tempo/game/`** — chess rules, board state, move legality (built on
  [`python-chess`](https://python-chess.readthedocs.io/)).
- **`src/tempo/mentor/`** — the difficulty controller, motif/tactic
  detector, and hint generation.

## Status

Early scaffolding — see `docs/PLAN.md` (coming soon) for the phased build
order. Nothing trains yet; this commit sets up the project skeleton and
data pipeline.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

You'll also need the [Stockfish](https://stockfishchess.org/) binary on
your PATH for ground-truth evaluation (used by the hint engine, not by the
move-prediction model itself).

## Getting training data

```bash
python -m tempo.data.download --month 2024-01 --min-rating 1200 --max-rating 1800
```

This pulls a Lichess monthly PGN archive (see
[database.lichess.org](https://database.lichess.org/)) and filters games to
a rating band, so you're not pulling the entire multi-hundred-GB archive
just to get started.
