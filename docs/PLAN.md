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
      (`tempo.mentor.hints`) — the eval number is always returned (it
      drives the eval bar; an earlier version hid it at low strength and
      froze the bar for most users). What scales with strength: low
      strength gets a plain-language label and only the single most
      concrete motif; mid gets the label and all motifs; high drops the
      label. Wired into `/game/hint` and the hint panel UI.
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
- [x] Deploy for real: backend live on Render
      (`https://chesstempo-api.onrender.com`, Docker, auto-deploys on push
      to `main`), Supabase project restored and schema current, frontend
      pushed to `main` for Vercel's git integration to pick up. Two real
      deploy-time bugs surfaced and fixed in the process (not caught by
      local tests, since neither reproduces outside a from-scratch Docker
      build): an unanchored `.gitignore` pattern that silently dropped a
      new source file from git, and a transitive dependency (`tqdm`) the
      backend needed for the first time once personalization landed but
      `backend/requirements.txt` never listed.
- [x] Checkpoint actually shipped to the live backend (Supabase Storage,
      `MODEL_CHECKPOINT_URL`) and verified end-to-end against a real
      signed-up user (`/game/move` and `/game/hint` both returned real,
      legal responses from the trained model + Stockfish).

      **Found and fixed a real memory problem in the process:** the first
      live `/game/move` call OOM-killed the container on Render's free
      512MB plan — confirmed both from Render logs (checkpoint loads
      fine, then the process dies with no further output, consistent
      with a hard kill rather than an app-level error) and from Render's
      own automated "exceeded its memory limit" alert. Two real causes,
      not one:
      1. PyTorch's CPU backend defaults its thread pool to the host's
         reported core count, which allocates real memory overhead on a
         tiny instance. Fixed: `OMP_NUM_THREADS` / `MKL_NUM_THREADS` /
         `OPENBLAS_NUM_THREADS` pinned to 1 before torch initializes
         (`backend/app/main.py`), plus `torch.set_num_threads(1)`.
      2. Plain `pip install torch` on Linux resolves to the CUDA-enabled
         build by default, bundling several hundred MB of unused
         `nvidia-*` runtime packages onto a box with no GPU. Fixed:
         install from PyTorch's CPU-only wheel index in
         `backend/Dockerfile` before the rest of the requirements.

      **Still true after both fixes — read before assuming this is fully
      solved:** measured memory after the fix sits around 456MB of the
      512MB limit after a single inference call (Render's own metrics,
      `get_metrics` on the service). That's a thin margin, not a wide
      one. `tempo.mentor.personalization`'s background fine-tune job
      loads a second full model copy plus an AdamW optimizer's worth of
      gradient state on top of whatever the request path is already
      holding — a real, not-yet-tested risk of the *same* OOM once a
      real user reaches the 10-game fine-tune threshold. If that
      happens: the fix is almost certainly Render's paid tier (more
      RAM), not more code — this is a resource ceiling, not a leak.
      Deliberately not making that upgrade call here; it costs money and
      is yours to decide, not something to do silently on your behalf.

## Phase 6 — Profile, tracking and account features
- [x] Insights on the profile page (`tempo.mentor.insights`, `/profile/insights`):
      current/best streaks, average game length, the openings the user
      actually reaches with their W/D/L in each (a small hand-picked
      opening table with longest-prefix matching, *not* a full ECO
      database — unmatched games fall back to a coarse first-move label),
      and milestones derived from existing stats.
- [x] Personalization status surfaced to the user (it previously ran
      silently): whether the bot has adapted, games until the next
      update, last update date, and whether the personalized model is
      actually loaded right now — the DB remembers a tune even after
      Render's ephemeral disk loses the checkpoint file, so the UI says
      so instead of claiming an adapted bot that isn't loaded.
- [x] Account settings (`/settings`): edit display name, reset difficulty
      (which really resets `strength` to that tier's start), change
      password, delete account (removes the auth user, cascading to
      profile/games/personalization rows, plus local personalization
      artifacts).
- [x] Forgot-password flow (login link -> Supabase reset email ->
      `/reset-password`). **Not verified end-to-end** — that needs a real
      inbox, and the app's `/reset-password` URL must be in Supabase's
      Auth -> URL Configuration redirect allow-list or the email link
      will fall back to the project's Site URL.
- [x] Resume an unfinished game after a closed tab/refresh
      (localStorage, per-browser — not synced across devices).
- [ ] Not built, deliberately: per-color stats (the user always plays
      White, so it would be meaningless), leaderboards/friends (one bot
      per user), puzzles, and accuracy-over-time (accuracy is only
      computed on demand by `/game/review` and isn't persisted per game;
      persisting it would mean running the slow engine review on every
      finished game, which the free-tier instance can't afford).

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
