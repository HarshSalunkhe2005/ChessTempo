"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";
import { HeroGlyphs } from "@/components/ChessArt";
import { DIFFICULTY_LABELS } from "@/lib/chessDisplay";

// Mirrors DifficultyController.STARTING_DIFFICULTY_MAP — the actual
// strength values live server-side (supabase/schema.sql's handle_new_user
// trigger); this is just what the picker shows.
const DIFFICULTY_HINTS: Record<string, string> = {
  beginner: "New to chess or still learning the rules",
  casual: "Play sometimes, know the basics well",
  club: "Play regularly, know openings and tactics",
  strong: "Tournament-level or near it",
};
const DIFFICULTY_OPTIONS = Object.keys(DIFFICULTY_LABELS);

export default function SignupPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [difficulty, setDifficulty] = useState("casual");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsConfirmation, setNeedsConfirmation] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { full_name: name, starting_difficulty: difficulty } },
    });

    setLoading(false);
    if (error) {
      setError(error.message);
      return;
    }

    if (data.session) {
      // Email confirmation is off — user's straight in.
      router.push("/play");
    } else {
      // Supabase requires confirming the email before a session is issued.
      setNeedsConfirmation(true);
    }
  };

  if (needsConfirmation) {
    return (
      <main className="page-center">
        <div className="card">
          <div className="brand">
            <span className="brand-mark">♞</span>
            <span className="brand-name">ChessTempo</span>
          </div>
          <p>
            Almost there — we sent a confirmation link to <strong>{email}</strong>. Click it to
            activate your account, then log in.
          </p>
          <Link href="/login" className="btn" style={{ display: "block", textAlign: "center", marginTop: 16 }}>
            Go to login
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="page-center">
      <HeroGlyphs />
      <div className="card">
        <div className="brand">
          <span className="brand-mark">♞</span>
          <span className="brand-name">ChessTempo</span>
        </div>
        <p className="subtitle">Create your account.</p>

        <form onSubmit={handleSubmit}>
          <input
            type="text"
            required
            placeholder="Your name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="field"
            autoFocus
          />
          <input
            type="email"
            required
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="field"
          />
          <input
            type="password"
            required
            minLength={8}
            placeholder="Password (min 8 characters)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="field"
          />

          <p className="subtitle" style={{ margin: "4px 0 8px" }}>
            How would you describe your chess level?
          </p>
          <div className="difficulty-picker">
            {DIFFICULTY_OPTIONS.map((key) => (
              <button
                type="button"
                key={key}
                className={`difficulty-option${difficulty === key ? " selected" : ""}`}
                onClick={() => setDifficulty(key)}
              >
                <span className="difficulty-option-label">{DIFFICULTY_LABELS[key]}</span>
                <span className="difficulty-option-hint">{DIFFICULTY_HINTS[key]}</span>
              </button>
            ))}
          </div>

          <button type="submit" className="btn" disabled={loading}>
            {loading && <span className="spinner" />}
            {loading ? "Creating account..." : "Sign up"}
          </button>
          {error && <p className="error-text">{error}</p>}
        </form>

        <p className="auth-switch">
          Already have an account? <Link href="/login">Log in</Link>
        </p>
      </div>
    </main>
  );
}
