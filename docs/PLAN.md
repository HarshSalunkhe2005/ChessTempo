# Build plan

Rough phased order, so we're not trying to build everything at once. Each
phase should be individually testable/demoable before moving to the next.

## Phase 1 — Base model
- [x] Board <-> tensor encoding, move <-> index encoding (`tempo.data.encoding`)
- [x] Lichess archive download + rating-band filter (`tempo.data.download`)
- [x] PGN -> sharded training data (`tempo.data.pgn_to_dataset`)
- [x] Model architecture (`tempo.model.net`) — 6-block residual CNN, ~10M params
- [x] Training loop (`tempo.model.train`)
- [x] Trained on a real (small) slice of Lichess data end-to-end and
      checked move-match accuracy against a held-out set — see
      `checkpoints/tempo_best.pt`. This was a deliberately small/fast run
      to prove the whole pipeline works, not a Maia-scale training run —
      it does **not** hit Maia's ~50% top-1 human-move-match bar. Scaling
      up (a recent, much larger monthly archive + a GPU + more epochs) is
      a config change to `tempo.data.download`/`tempo.model.train`, not a
      code change.

      **Run notes:** `lichess_db_standard_rated_2013-01` (an early, small
      archive — ~18MB compressed — chosen so the whole pipeline could run
      on CPU in minutes rather than needing a multi-GB download and a
      GPU), filtered to the 1000–2000 rating band, capped at 6,000 games
      (~393K positions, `tempo.data.download --month 2013-01 --min-rating
      1000 --max-rating 2000 --max-games 6000`). 3 epochs, batch size 128,
      1 shard (~33K positions) held out for validation:

      | Epoch | Train loss | Val move-match accuracy |
      |-------|-----------|--------------------------|
      | 1     | 3.50      | 27.2%                    |
      | 2     | 2.32      | 29.6%                    |
      | 3     | 1.93      | 29.9%                    |

      Accuracy was still climbing at epoch 3 — more data/epochs would
      keep improving it further before hitting Maia-scale territory.
      Manually spot-checked too: sampling moves from the trained model
      (no engine blending) on the opening position produced a coherent,
      book-like sequence (1. e4 e6 2. Nf3 d5 3. e5 c6), not noise.

      This run also surfaced and fixed a real bug in
      `tempo.data.shard_dataset.ShardedPositionDataset`: its one-shard
      cache assumed roughly sequential access, but `DataLoader(...,
      shuffle=True)` (used by both `tempo.model.train` and
      `tempo.model.finetune`) draws a fresh random global index per
      sample — with more than a couple of shards that misses the cache
      almost every time, forcing a full shard reload+decompress per
      sample. Concretely: ~30 seconds/batch instead of ~0.2s/batch on this
      run's 10 shards. Fixed with `ShardShuffleSampler` (shuffles shard
      order and within-shard order, but never interleaves shards) plus a
      shard-level train/val split in `tempo.model.train` — see that
      module's comments. Worth knowing about before scaling this run up:
      the bug doesn't go away with more data, it gets worse.

## Phase 2 — Personalization
- [x] Fine-tuning script skeleton (`tempo.model.finetune`)
- [x] Game logging: store every move you play against the bot, in the same
      shard format as training data, per-user (`tempo.data.game_log`,
      wired into `backend/app/personalization.py`) — only the user's own
      moves are logged, since personalization predicts *their* patterns,
      not the bot's own replies.
- [x] Decide fine-tune cadence and wire it up to run automatically: every
      `GAMES_PER_FINETUNE` (10) games, as a FastAPI background task after
      `/game/finish` (`tempo.mentor.personalization`) — no separate
      nightly job needed for a single-instance backend.
- [ ] Evaluate: does move-match accuracy on *your* held-out games improve
      after fine-tuning vs. the base model alone? Needs a real user
      playing enough games to fine-tune against — can't be validated with
      synthetic data alone.

## Phase 3 — Difficulty auto-adjustment
- [x] Difficulty controller skeleton (`tempo.mentor.difficulty`)
- [x] Move selection blending model output with Stockfish (`tempo.game.play`)
- [x] Wire outcome tracking (win/loss, closeness) into the controller after
      each real game — `tempo.mentor.review.estimate_game_closeness` evals
      the position right before the game's last move and feeds that into
      `DifficultyController.update_after_game`, in `backend/app/main.py`'s
      `/game/finish`.
- [ ] Playtest: does the strength curve feel like it's actually adapting,
      or does it swing too fast/slow? Tune `k_factor`. This is inherently
      a real-usage question — no amount of code review substitutes for
      someone actually playing games against it.

## Phase 4 — Hint / mentor layer
- [x] Stockfish oracle wrapper (`tempo.game.engine`)
- [x] Rule-based motif detection: hanging pieces, forks, pins, skewers,
      back-rank weaknesses, discovered-attack threats (`tempo.mentor.motifs`)
- [x] Hint verbosity scaling based on current difficulty/skill estimate
      (`tempo.mentor.hints`) — low strength hides the raw eval number in
      favor of a plain-language read and caps to the single most concrete
      motif; high strength shows the raw number and drops the plain-
      language label. Wired into `/game/hint` and the hint panel UI.
- [x] Actual UI/app to play against and view hints in — see Phase 5.

## Phase 5 — Web app
Decided: a backend API (FastAPI, wrapping `tempo/` directly) + a Next.js/PWA
frontend, so playing the game needs nothing but a browser — no git clone,
no Python, no GPU. See the root README's "Running the whole stack locally"
and "Deploying for free" sections.

- [x] Supabase schema: profiles, game history, RLS policies (`supabase/schema.sql`)
- [x] FastAPI backend: `/profile`, `/game/move`, `/game/hint`, `/game/finish`
      (`backend/app/`)
- [x] JWT auth verification against Supabase-issued tokens (`backend/app/auth.py`)
- [x] Dockerfile bundling Stockfish, for Render deployment
- [x] Next.js frontend: magic-link login, chessboard, hint panel, PWA manifest
- [x] Starting-difficulty picker at signup, wired to
      `DifficultyController.STARTING_DIFFICULTY_MAP` via the
      `handle_new_user` Supabase trigger
- [x] Real app icons for the PWA manifest (`scripts/gen_icons.py` generates
      `frontend/public/icon-192.png` / `icon-512.png` from the same
      knight-glyph brand mark used elsewhere in the app)
- [x] Decide how the trained checkpoint gets to the deployed backend:
      `MODEL_CHECKPOINT_URL` (optional) — if set and
      `MODEL_CHECKPOINT_PATH` doesn't exist locally, the backend downloads
      it once at first use and caches it on disk. Point it at a Supabase
      Storage public/signed URL, or leave it unset and upload the
      checkpoint to the server by hand.
- [ ] Deploy for real: Render (backend) + Vercel (frontend) + Supabase, and
      confirm the full loop works end-to-end against a live checkpoint —
      needs real accounts on those services; see the README's "Deploying
      for free" section for the steps.

## Open questions to revisit
- How much of a user's game history is "enough" before the first
  fine-tune is worth running? Currently a flat 10-game cadence
  (`tempo.mentor.personalization.GAMES_PER_FINETUNE`) regardless of how
  decisive/instructive those games were — a quality-weighted trigger is a
  reasonable follow-up once there's real usage to tune it against.
- Per-user model storage: full checkpoint per user vs. a smaller
  fine-tuned delta/adapter, once there are enough users for storage to
  matter on Supabase's free tier. Currently a full checkpoint per
  personalized user under `checkpoints/personalized/`.
