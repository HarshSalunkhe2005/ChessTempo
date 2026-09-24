// Persists the in-progress game's PGN so closing the tab (or a page
// refresh) mid-game doesn't lose it. localStorage, not sessionStorage —
// it should survive a closed tab. Per-browser, not per-account; a
// different device won't see it.
const KEY = "chesstempo_active_game";

export function saveActiveGame(pgn: string): void {
  try {
    localStorage.setItem(KEY, pgn);
  } catch {
    // storage disabled — resuming just won't be available
  }
}

export function loadActiveGame(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function clearActiveGame(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // nothing to do
  }
}
