"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";
import { HeroGlyphs } from "@/components/ChessArt";

// Landing page for the link in Supabase's password-reset email. supabase-js
// reads the recovery token out of the URL on load and fires a
// PASSWORD_RECOVERY auth event, which is what unlocks the form below.
export default function ResetPasswordPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [expired, setExpired] = useState(false);
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    const { data } = supabase.auth.onAuthStateChange((event) => {
      if (event === "PASSWORD_RECOVERY") setReady(true);
    });
    // If the token was already consumed before this listener attached, a
    // session may exist; otherwise after a short grace period call it
    // expired rather than leaving a blank page.
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) setReady(true);
    });
    const timer = setTimeout(() => setExpired(true), 4000);
    return () => {
      data.subscription.unsubscribe();
      clearTimeout(timer);
    };
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const { error } = await supabase.auth.updateUser({ password });
    setLoading(false);
    if (error) {
      setError(error.message);
    } else {
      setDone(true);
      setTimeout(() => router.push("/play"), 1500);
    }
  };

  return (
    <main className="page-center">
      <HeroGlyphs />
      <div className="card">
        <div className="brand">
          <span className="brand-mark">♞</span>
          <span className="brand-name">ChessTempo</span>
        </div>

        {done ? (
          <p className="subtitle">Password updated — taking you to the board...</p>
        ) : ready ? (
          <>
            <p className="subtitle">Choose a new password.</p>
            <form onSubmit={submit}>
              <input
                type="password"
                required
                minLength={8}
                placeholder="New password (min 8 characters)"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="field"
                autoFocus
              />
              <button type="submit" className="btn" disabled={loading}>
                {loading ? "Saving..." : "Set new password"}
              </button>
              {error && <p className="error-text">{error}</p>}
            </form>
          </>
        ) : expired ? (
          <>
            <p className="subtitle">This reset link is invalid or has expired.</p>
            <Link href="/login" className="btn" style={{ display: "block", textAlign: "center" }}>
              Back to login
            </Link>
          </>
        ) : (
          <p className="subtitle">Checking your reset link...</p>
        )}
      </div>
    </main>
  );
}
