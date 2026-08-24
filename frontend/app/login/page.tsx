"use client";

import { useState } from "react";
import { supabase } from "@/lib/supabaseClient";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    // Magic link — no passwords to manage, matches the "not tech-savvy
    // friendly" goal: click a link in your inbox, you're in.
    const { error } = await supabase.auth.signInWithOtp({ email });
    if (error) setError(error.message);
    else setSent(true);
  };

  if (sent) {
    return (
      <main style={{ padding: 32, maxWidth: 420, margin: "0 auto" }}>
        <h1>Check your email</h1>
        <p>We sent a login link to {email}.</p>
      </main>
    );
  }

  return (
    <main style={{ padding: 32, maxWidth: 420, margin: "0 auto" }}>
      <h1>ChessTempo</h1>
      <p>A chess mentor that grows with you.</p>
      <form onSubmit={handleSubmit}>
        <input
          type="email"
          required
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          style={{ width: "100%", padding: 10, fontSize: 16, marginBottom: 12 }}
        />
        <button type="submit" style={{ width: "100%", padding: 10, fontSize: 16 }}>
          Send login link
        </button>
      </form>
      {error && <p style={{ color: "salmon" }}>{error}</p>}
    </main>
  );
}
