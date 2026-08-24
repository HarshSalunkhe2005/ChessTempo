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

Early scaffolding — see `docs/PLAN.md` for the phased build order.

## Project layout

```
src/tempo/       the core Python package: model, data pipeline, mentor logic
backend/         FastAPI app that wraps tempo/ behind an HTTP API
frontend/        Next.js + PWA web app (chessboard, login, hints)
supabase/        SQL schema (auth, profiles, game history)
```

The web app (`backend/` + `frontend/`) is how end users will actually play —
nobody needs to clone this repo or touch Python to use it. Training the
model (`src/tempo/model`) is a separate, one-time-ish offline step you run
yourself; the resulting checkpoint is what the backend serves.

## Running the whole stack locally

**1. Supabase** — create a free project at [supabase.com](https://supabase.com),
then run `supabase/schema.sql` in its SQL Editor. Grab the project URL, the
`anon` key, the `service_role` key, and the JWT secret (Settings → API).

**2. Backend**
```bash
cd backend
cp .env.example .env   # fill in your Supabase values
python -m venv .venv && source .venv/bin/activate
pip install -e ..
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Needs the [Stockfish](https://stockfishchess.org/) binary on your PATH
locally (the Docker image installs it automatically for deployment).

**3. Frontend**
```bash
cd frontend
cp .env.local.example .env.local   # fill in your Supabase anon key + API URL
npm install
npm run dev
```
Open http://localhost:3000 — you'll land on the login page (magic-link
email, no password), then the board.

## Deploying for free

- **Backend → [Render](https://render.com)**: New → Blueprint → point it at
  this repo (uses `render.yaml` + `backend/Dockerfile`, which bundles
  Stockfish). Set the Supabase env vars in Render's dashboard — never in
  the repo.
- **Frontend → [Vercel](https://vercel.com)**: New Project → point it at
  this repo with root directory `frontend/`. Set the `NEXT_PUBLIC_*` env
  vars in Vercel's dashboard.
- **Database/Auth → [Supabase](https://supabase.com)** free tier, already
  set up in step 1 above.

None of this costs anything at free-tier usage. See `docs/PLAN.md` for the
trade-offs (e.g. Render's free tier sleeps when idle).

**Note:** the backend needs a trained model checkpoint to actually play
well — without one it falls back to a randomly-initialized model (functional,
just not good) so the API doesn't crash. See "Getting training data" and
`docs/PLAN.md` Phase 1 for training your own, then set
`MODEL_CHECKPOINT_PATH` to point at it once deployed (the checkpoint file
itself isn't committed to git — it's a large binary artifact — so decide
how you want to ship it to the backend, e.g. Supabase Storage or Git LFS,
once you have one worth deploying).

## Local Python setup (for training/data work)

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
