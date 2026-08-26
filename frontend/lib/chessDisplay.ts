// Shared display helpers used by both the game screen and the profile
// page, so the "rating" shown for a given strength (etc.) stays
// consistent across the app instead of drifting between copies.

export const DIFFICULTY_LABELS: Record<string, string> = {
  beginner: "Beginner",
  casual: "Casual",
  club: "Club",
  strong: "Strong",
};

const FIGURINE: Record<string, string> = { N: "♞", B: "♝", R: "♜", Q: "♛", K: "♚" };

/** SAN like "Nf3" -> "♞f3" — figurine notation, as used in most move lists. */
export function toFigurine(san: string): string {
  const glyph = FIGURINE[san[0]];
  return glyph ? glyph + san.slice(1) : san;
}

/** Maps our 0-1 difficulty "strength" to a familiar chess-rating-looking
 * number, purely cosmetic — there's no real rating system underneath yet. */
export function strengthToRating(strength: number): number {
  return Math.round(400 + strength * 2000);
}

export function initials(name: string): string {
  return name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

// Move-quality classification colors — shared between the move list (once
// it shows review results) and the profile/game-review views.
export const CLASSIFICATION_COLOR: Record<string, string> = {
  Brilliant: "#1baaa6",
  Best: "#57b37a",
  Excellent: "#57b37a",
  Good: "#9aa2b1",
  Book: "#9aa2b1",
  Inaccuracy: "#d9a441",
  Mistake: "#e08a3c",
  Blunder: "#e5674f",
};
