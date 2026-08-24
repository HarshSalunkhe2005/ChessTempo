"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { supabase } from "@/lib/supabaseClient";
import { BoardPattern, HeroGlyphs } from "@/components/ChessArt";

const FEATURES = [
  {
    icon: "♟",
    title: "Grows with you",
    body: "No fixed rating. The bot's strength adjusts automatically based on how your games actually go.",
  },
  {
    icon: "♞",
    title: "Learns your patterns",
    body: "Trained to play like a human, then personalized to your own moves as you play more games.",
  },
  {
    icon: "♛",
    title: "Hints in plain English",
    body: "\"Watch your knight\" instead of a raw eval number — tactical explanations you can actually use.",
  },
  {
    icon: "♚",
    title: "Free, always",
    body: "No subscription, no paywall. Just open the page and play.",
  },
];

export default function LandingPage() {
  const [loggedIn, setLoggedIn] = useState<boolean | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setLoggedIn(!!session);
    });
  }, []);

  return (
    <main>
      <nav className="nav">
        <div className="nav-brand">
          <span className="brand-mark">♞</span>
          <span className="brand-name">ChessTempo</span>
        </div>
        <div className="nav-links">
          {loggedIn ? (
            <Link href="/play" className="btn btn-small">
              Play
            </Link>
          ) : (
            <>
              <Link href="/login" className="btn-secondary">
                Log in
              </Link>
              <Link href="/signup" className="btn btn-small">
                Sign up
              </Link>
            </>
          )}
        </div>
      </nav>

      <section className="hero">
        <BoardPattern />
        <HeroGlyphs />
        <div className="hero-content">
          <h1>A chess mentor that grows with you.</h1>
          <p className="hero-sub">
            Not a fixed-ELO bot. ChessTempo learns how you play, adapts its difficulty as you
            improve, and explains what's happening on the board in plain language.
          </p>
          <div className="hero-cta">
            <Link href={loggedIn ? "/play" : "/signup"} className="btn">
              {loggedIn ? "Continue playing" : "Get started — it's free"}
            </Link>
            {!loggedIn && (
              <Link href="/login" className="btn-secondary">
                I already have an account
              </Link>
            )}
          </div>
        </div>
      </section>

      <section className="features">
        {FEATURES.map((f) => (
          <div className="feature-card" key={f.title}>
            <div className="feature-icon">{f.icon}</div>
            <h3>{f.title}</h3>
            <p>{f.body}</p>
          </div>
        ))}
      </section>

      <footer className="footer">
        <p>
          ChessTempo is an open project.{" "}
          <a href="https://github.com/HarshSalunkhe2005/ChessTempo" target="_blank" rel="noreferrer">
            Source on GitHub
          </a>
        </p>
      </footer>
    </main>
  );
}
