// Hand-built decorative art — no external/hotlinked images, so nothing to
// break, license, or wait on. A subtle chessboard texture plus oversized,
// semi-transparent piece glyphs for visual weight in the hero section.

export function BoardPattern() {
  return (
    <svg
      aria-hidden
      className="board-pattern"
      viewBox="0 0 400 400"
      preserveAspectRatio="xMidYMid slice"
    >
      <defs>
        <pattern id="checker" width="50" height="50" patternUnits="userSpaceOnUse">
          <rect width="50" height="50" fill="transparent" />
          <rect width="25" height="25" fill="currentColor" opacity="0.06" />
          <rect x="25" y="25" width="25" height="25" fill="currentColor" opacity="0.06" />
        </pattern>
      </defs>
      <rect width="400" height="400" fill="url(#checker)" />
    </svg>
  );
}

export function HeroGlyphs() {
  return (
    <div className="hero-glyphs" aria-hidden>
      <span className="glyph glyph-knight">♞</span>
      <span className="glyph glyph-king">♚</span>
    </div>
  );
}
