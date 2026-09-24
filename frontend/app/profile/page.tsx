"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { supabase } from "@/lib/supabaseClient";
import { api, GameSummary, ProfileInsights, ProfileResponse, ProfileStats } from "@/lib/api";
import { DIFFICULTY_LABELS, initials, strengthToRating } from "@/lib/chessDisplay";
import { setReviewHandoff } from "@/lib/reviewHandoff";
import RatingChart from "@/components/RatingChart";

const RESULT_LABEL: Record<string, { text: string; color: string }> = {
  user_win: { text: "Win", color: "var(--success)" },
  user_loss: { text: "Loss", color: "var(--danger)" },
  draw: { text: "Draw", color: "var(--text-dim)" },
};

function streakLabel(streak: ProfileInsights["streak"]): string {
  if (!streak.current_result || streak.current_length === 0) return "—";
  const kind = streak.current_result === "user_win" ? "W" : streak.current_result === "user_loss" ? "L" : "D";
  return `${streak.current_length}${kind}`;
}

function milestones(stats: ProfileStats, insights: ProfileInsights) {
  return [
    { label: "First game", hint: "Play a game", done: stats.total_games >= 1 },
    { label: "First win", hint: "Beat the bot once", done: stats.wins >= 1 },
    { label: "Regular", hint: "Play 10 games", done: stats.total_games >= 10 },
    { label: "Veteran", hint: "Play 25 games", done: stats.total_games >= 25 },
    { label: "Hot streak", hint: "Win 3 in a row", done: insights.streak.best_win_streak >= 3 },
    {
      label: "Known quantity",
      hint: "Your bot adapts to your style",
      done: insights.personalization.last_finetuned_at != null,
    },
  ];
}

export default function ProfilePage() {
  const router = useRouter();
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [stats, setStats] = useState<ProfileStats | null>(null);
  const [games, setGames] = useState<GameSummary[]>([]);
  const [insights, setInsights] = useState<ProfileInsights | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        router.replace("/login");
        return;
      }
      setCheckingAuth(false);
      Promise.all([api.getProfile(), api.getProfileStats(), api.getGames()])
        .then(([p, s, g]) => {
          setProfile(p);
          setStats(s);
          setGames(g);
        })
        .catch((e) => setError(e.message));
      api.getProfileInsights().then(setInsights).catch(() => {});
    });
  }, [router]);

  if (checkingAuth) return null;

  return (
    <div className="play-shell">
      <nav className="nav">
        <Link href="/" className="nav-brand" style={{ textDecoration: "none", color: "inherit" }}>
          <span className="brand-mark">♞</span>
          <span className="brand-name">ChessTempo</span>
        </Link>
        <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
          <Link href="/play" className="btn-link" style={{ textDecoration: "none" }}>
            Play
          </Link>
          <Link href="/settings" className="btn-link" style={{ textDecoration: "none" }}>
            Settings
          </Link>
          <button
            className="btn-link"
            onClick={async () => {
              await supabase.auth.signOut();
              router.push("/");
            }}
          >
            Log out
          </button>
        </div>
      </nav>

      <div style={{ maxWidth: 720, margin: "0 auto", padding: "44px 32px" }}>
        {error && <p className="error-text">{error}</p>}

        {profile && (
          <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 32 }}>
            <span className="avatar avatar-user" style={{ width: 64, height: 64, fontSize: 24 }}>
              {initials(profile.full_name || "You")}
            </span>
            <div>
              <h1 style={{ fontFamily: "var(--font-display)", fontSize: 26, margin: 0 }}>
                {profile.full_name || "Anonymous player"}
              </h1>
              <p style={{ color: "var(--text-dim)", margin: "4px 0 0" }}>
                {DIFFICULTY_LABELS[profile.starting_difficulty] ?? profile.starting_difficulty} ·{" "}
                {strengthToRating(profile.strength)} rating
              </p>
            </div>
          </div>
        )}

        {stats && (
          <div className="stat-grid">
            <div className="stat-tile">
              <div className="stat-tile-value">{stats.total_games}</div>
              <div className="stat-tile-label">Games played</div>
            </div>
            <div className="stat-tile">
              <div className="stat-tile-value" style={{ color: "var(--success)" }}>
                {stats.wins}
              </div>
              <div className="stat-tile-label">Wins</div>
            </div>
            <div className="stat-tile">
              <div className="stat-tile-value" style={{ color: "var(--danger)" }}>
                {stats.losses}
              </div>
              <div className="stat-tile-label">Losses</div>
            </div>
            <div className="stat-tile">
              <div className="stat-tile-value">{stats.draws}</div>
              <div className="stat-tile-label">Draws</div>
            </div>
            <div className="stat-tile">
              <div className="stat-tile-value">{stats.win_rate != null ? `${stats.win_rate}%` : "—"}</div>
              <div className="stat-tile-label">Win rate</div>
            </div>
          </div>
        )}

        {insights && stats && (
          <>
            <div className="stat-grid" style={{ marginTop: 16 }}>
              <div className="stat-tile">
                <div className="stat-tile-value">{streakLabel(insights.streak)}</div>
                <div className="stat-tile-label">Current streak</div>
              </div>
              <div className="stat-tile">
                <div className="stat-tile-value">{insights.streak.best_win_streak}</div>
                <div className="stat-tile-label">Best win streak</div>
              </div>
              <div className="stat-tile">
                <div className="stat-tile-value">{insights.avg_moves_per_game ?? "—"}</div>
                <div className="stat-tile-label">Avg. moves / game</div>
              </div>
            </div>

            <div className="panel-card" style={{ marginTop: 24 }}>
              <div className="status-eyebrow">Your bot</div>
              <p style={{ margin: "0 0 4px", fontSize: 15 }}>
                {insights.personalization.last_finetuned_at
                  ? insights.personalization.model_active
                    ? "Your bot has adapted to your play style."
                    : "Your bot was adapted to your style, but its personalized model isn't loaded right now (the server restarted) — it'll rebuild after your next few games."
                  : "Your bot hasn't adapted to you yet."}
              </p>
              <p className="hint-eval" style={{ margin: 0 }}>
                {insights.personalization.games_until_next_tune === 0
                  ? "Next game triggers a personalization update."
                  : `${insights.personalization.games_until_next_tune} more game${
                      insights.personalization.games_until_next_tune === 1 ? "" : "s"
                    } until its next update.`}
                {insights.personalization.last_finetuned_at &&
                  ` Last updated ${new Date(insights.personalization.last_finetuned_at).toLocaleDateString()}.`}
              </p>
            </div>

            {insights.openings.length > 0 && (
              <div className="move-list" style={{ marginTop: 24 }}>
                <h3>Openings you reach</h3>
                <div className="move-list-body" style={{ maxHeight: "none" }}>
                  {insights.openings.map((o) => (
                    <div
                      key={o.name}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        padding: "10px 6px",
                        borderBottom: "1px solid var(--border)",
                        fontSize: 14,
                      }}
                    >
                      <span style={{ fontWeight: 600 }}>{o.name}</span>
                      <span className="hint-eval">
                        {o.games} game{o.games === 1 ? "" : "s"} ·{" "}
                        <span style={{ color: "var(--success)" }}>{o.wins}W</span>{" "}
                        <span>{o.draws}D</span>{" "}
                        <span style={{ color: "var(--danger)" }}>{o.losses}L</span>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="panel-card" style={{ marginTop: 24 }}>
              <div className="status-eyebrow">Milestones</div>
              <div className="milestone-grid">
                {milestones(stats, insights).map((m) => (
                  <div key={m.label} className={`milestone${m.done ? "" : " milestone-locked"}`} title={m.hint}>
                    <div className="milestone-label">{m.label}</div>
                    <div className="milestone-hint">{m.hint}</div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {games.length > 1 && (
          <div className="panel-card" style={{ marginTop: 32 }}>
            <div className="status-eyebrow">Rating over time</div>
            <RatingChart games={games} />
          </div>
        )}

        <div className="move-list" style={{ marginTop: 32 }}>
          <h3>Recent games</h3>
          <div className="move-list-body" style={{ maxHeight: "none" }}>
            {games.length === 0 && <p className="hint-eval">No games played yet — go play one!</p>}
            {games.map((g) => {
              const label = RESULT_LABEL[g.result] ?? { text: g.result, color: "var(--text-dim)" };
              return (
                <div
                  key={g.id}
                  className="move-san-clickable"
                  onClick={() => {
                    setReviewHandoff({ pgn: g.pgn, result: g.result });
                    router.push("/play");
                  }}
                  title="Click to review this game move by move"
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "10px 6px",
                    borderBottom: "1px solid var(--border)",
                  }}
                >
                  <span style={{ fontWeight: 700, color: label.color }}>{label.text}</span>
                  <span className="hint-eval">
                    {strengthToRating(g.strength_at_start)} → {strengthToRating(g.strength_at_end)}
                  </span>
                  <span className="hint-eval">{new Date(g.created_at).toLocaleDateString()}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
