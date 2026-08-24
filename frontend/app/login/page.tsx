"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Secondary path for anyone who'd rather not type a password — sends a
  // one-click login link instead. Kept as a fallback, not the default,
  // per the "needs real accounts" ask.
  const [magicLinkSent, setMagicLinkSent] = useState(false);
  const [magicLinkLoading, setMagicLinkLoading] = useState(false);

  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setLoading(false);
    if (error) setError(error.message);
    else router.push("/play");
  };

  const handleMagicLink = async () => {
    if (!email) {
      setError("Enter your email above first.");
      return;
    }
    setError(null);
    setMagicLinkLoading(true);
    const { error } = await supabase.auth.signInWithOtp({ email });
    setMagicLinkLoading(false);
    if (error) setError(error.message);
    else setMagicLinkSent(true);
  };

  return (
    <main className="page-center">
      <div className="card">
        <div className="brand">
          <span className="brand-mark">♞</span>
          <span className="brand-name">ChessTempo</span>
        </div>
        <p className="subtitle">Welcome back.</p>

        <form onSubmit={handlePasswordLogin}>
          <input
            type="email"
            required
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="field"
            autoFocus
          />
          <input
            type="password"
            required
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="field"
          />
          <button type="submit" className="btn" disabled={loading}>
            {loading && <span className="spinner" />}
            {loading ? "Logging in..." : "Log in"}
          </button>
          {error && <p className="error-text">{error}</p>}
        </form>

        <div className="divider">or</div>

        {magicLinkSent ? (
          <p className="hint-eval">Check {email} for a login link.</p>
        ) : (
          <button
            type="button"
            className="btn btn-secondary"
            style={{ width: "100%" }}
            onClick={handleMagicLink}
            disabled={magicLinkLoading}
          >
            {magicLinkLoading ? "Sending..." : "Email me a login link instead"}
          </button>
        )}

        <p className="auth-switch">
          New here? <Link href="/signup">Create an account</Link>
        </p>
      </div>
    </main>
  );
}
