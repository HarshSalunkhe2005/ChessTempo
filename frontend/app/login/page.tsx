"use client";

import { useState } from "react";
import { supabase } from "@/lib/supabaseClient";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    // Magic link — no passwords to manage, matches the "not tech-savvy
    // friendly" goal: click a link in your inbox, you're in.
    const { error } = await supabase.auth.signInWithOtp({ email });
    setLoading(false);
    if (error) setError(error.message);
    else setSent(true);
  };

  return (
    <main className="page-center">
      <div className="card">
        <div className="brand">
          <span className="brand-mark">♞</span>
          <span className="brand-name">ChessTempo</span>
        </div>
        <p className="subtitle">A chess mentor that grows with you.</p>

        {sent ? (
          <p>
            Check <strong>{email}</strong> for a login link.
          </p>
        ) : (
          <form onSubmit={handleSubmit}>
            <input
              type="email"
              required
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="field"
              autoFocus
            />
            <button type="submit" className="btn" disabled={loading}>
              {loading && <span className="spinner" />}
              {loading ? "Sending..." : "Send login link"}
            </button>
            {error && <p className="error-text">{error}</p>}
          </form>
        )}
      </div>
    </main>
  );
}
