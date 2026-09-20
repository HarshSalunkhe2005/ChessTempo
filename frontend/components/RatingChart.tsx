// A small, dependency-free rating-over-time line — the games list already
// carries strength_at_end per game, so this is just an SVG polyline, not
// a charting library.
import { GameSummary } from "@/lib/api";
import { strengthToRating } from "@/lib/chessDisplay";

const WIDTH = 640;
const HEIGHT = 120;
const PADDING = 16;

export default function RatingChart({ games }: { games: GameSummary[] }) {
  // `games` comes back newest-first from the API; the chart reads
  // left-to-right chronologically.
  const chronological = [...games].reverse();
  const ratings = chronological.map((g) => strengthToRating(g.strength_at_end));

  const min = Math.min(...ratings);
  const max = Math.max(...ratings);
  const span = Math.max(1, max - min);

  const points = ratings.map((r, i) => {
    const x = ratings.length === 1 ? WIDTH / 2 : PADDING + (i / (ratings.length - 1)) * (WIDTH - PADDING * 2);
    const y = HEIGHT - PADDING - ((r - min) / span) * (HEIGHT - PADDING * 2);
    return [x, y] as const;
  });

  const path = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const latest = ratings[ratings.length - 1];

  return (
    <div style={{ overflowX: "auto" }}>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} width="100%" height={HEIGHT} preserveAspectRatio="none">
        <line
          x1={PADDING}
          y1={HEIGHT - PADDING}
          x2={WIDTH - PADDING}
          y2={HEIGHT - PADDING}
          stroke="var(--border)"
          strokeWidth={1}
        />
        <path d={path} fill="none" stroke="var(--accent)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {points.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r={i === points.length - 1 ? 4 : 2.5} fill="var(--accent)" />
        ))}
      </svg>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--text-dim)" }}>
        <span>{ratings[0]}</span>
        <span style={{ color: "var(--accent)", fontWeight: 700 }}>{latest}</span>
      </div>
    </div>
  );
}
