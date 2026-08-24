# Build plan

Rough phased order, so we're not trying to build everything at once. Each
phase should be individually testable/demoable before moving to the next.

## Phase 1 — Base model (in progress)
- [x] Board <-> tensor encoding, move <-> index encoding (`tempo.data.encoding`)
- [x] Lichess archive download + rating-band filter (`tempo.data.download`)
- [x] PGN -> sharded training data (`tempo.data.pgn_to_dataset`)
- [x] Model architecture (`tempo.model.net`) — 6-block residual CNN, ~9M params
- [x] Training loop (`tempo.model.train`)
- [ ] Actually train on a real slice of Lichess data and check move-match
      accuracy against a held-out set (Maia reports ~50% top-1 human move
      match at similar model scale — that's the bar to compare against)

## Phase 2 — Personalization
- [x] Fine-tuning script skeleton (`tempo.model.finetune`)
- [ ] Game logging: store every move you play against the bot, in the same
      shard format as training data, per-user
- [ ] Decide fine-tune cadence (every N games? nightly?) and wire it up to
      run automatically
- [ ] Evaluate: does move-match accuracy on *your* held-out games improve
      after fine-tuning vs. the base model alone?

## Phase 3 — Difficulty auto-adjustment
- [x] Difficulty controller skeleton (`tempo.mentor.difficulty`)
- [x] Move selection blending model output with Stockfish (`tempo.game.play`)
- [ ] Wire outcome tracking (win/loss, closeness) into the controller after
      each real game
- [ ] Playtest: does the strength curve feel like it's actually adapting,
      or does it swing too fast/slow? Tune `k_factor`.

## Phase 4 — Hint / mentor layer
- [x] Stockfish oracle wrapper (`tempo.game.engine`)
- [x] Rule-based motif detection: hanging pieces, forks (`tempo.mentor.motifs`)
- [ ] More motifs: pins, skewers, back-rank weaknesses, discovered attacks
- [ ] Hint verbosity scaling based on current difficulty/skill estimate
- [ ] Actual UI/app to play against and view hints in — see Phase 5, below

## Phase 5 — Web app (in progress)
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
- [ ] Deploy for real: Render (backend) + Vercel (frontend) + Supabase, and
      confirm the full loop works end-to-end against a live checkpoint
- [ ] Decide how the trained checkpoint gets to the deployed backend
      (it's a large binary, not committed to git — options: Supabase
      Storage download-on-boot, Git LFS, or a manual upload step)
- [ ] Real app icons for the PWA manifest (currently referenced but not
      generated — `frontend/public/icon-192.png` / `icon-512.png`)
- [ ] Hint verbosity scaling (ties back into Phase 4) once there's a UI to
      actually show it in

## Open questions to revisit
- How much of a user's game history is "enough" before the first
  fine-tune is worth running?
- Per-user model storage: full checkpoint per user vs. a smaller
  fine-tuned delta/adapter, once there are enough users for storage to
  matter on Supabase's free tier.
