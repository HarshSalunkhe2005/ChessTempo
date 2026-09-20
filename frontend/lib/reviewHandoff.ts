// Hands a finished game's PGN from the profile page to the game screen so
// clicking a past game can drop straight into move-by-move review — no
// backend round trip needed since /games already returns the full PGN.
// sessionStorage (not React context/router state) because the profile
// page and /play are separate route trees with a full navigation between
// them.
const KEY = "chesstempo_review_handoff";

export interface ReviewHandoff {
  pgn: string;
  result: "user_win" | "user_loss" | "draw";
}

export function setReviewHandoff(payload: ReviewHandoff): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(payload));
  } catch {
    // Private browsing / storage disabled — the game screen just won't
    // find anything and will start a fresh game instead, same as usual.
  }
}

export function takeReviewHandoff(): ReviewHandoff | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    sessionStorage.removeItem(KEY);
    return JSON.parse(raw) as ReviewHandoff;
  } catch {
    return null;
  }
}
