"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { supabase } from "@/lib/supabaseClient";
import { api, GameSummary, ProfileResponse, ProfileStats } from "@/lib/api";
import { DIFFICULTY_LABELS, initials, strengthToRating } from "@/lib/chessDisplay";

const RESULT_LABEL: Record<string, { text: string; color: string }> = {
  user_win: { text: "Win", color: "var(--success)" },
  user_loss: { text: "Loss", color: "var(--danger)" },
  draw: { text: "Draw", color: "var(--text-dim)" },
};

export default function ProfilePage() {
  const router = useRouter();
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [stats, setStats] = useState<ProfileStats | null>(null);
  const [games, setGames] = useState<GameSummary[]>([]);
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

        <div className="move-list" style={{ marginTop: 32 }}>
          <h3>Recent games</h3>
          <div className="move-list-body" style={{ maxHeight: "none" }}>
            {games.length === 0 && <p className="hint-eval">No games played yet — go play one!</p>}
            {games.map((g) => {
              const label = RESULT_LABEL[g.result] ?? { text: g.result, color: "var(--text-dim)" };
              return (
                <div
                  key={g.id}
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
