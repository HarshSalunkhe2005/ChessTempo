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
- [ ] Actual UI/app to play against and view hints in (not yet started —
      decide web app vs. mobile vs. CLI-first for early testing)

## Open questions to revisit
- Where does training/inference run for the shipped app — locally,
  or a backend server the client talks to?
- How much of a user's game history is "enough" before the first
  fine-tune is worth running?
