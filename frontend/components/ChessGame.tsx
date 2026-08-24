"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import { api, HintResponse, ProfileResponse } from "@/lib/api";
import { supabase } from "@/lib/supabaseClient";
import { useRouter } from "next/navigation";

const DIFFICULTY_LABELS: Record<string, string> = {
  beginner: "Beginner",
  casual: "Casual",
  club: "Club",
  strong: "Strong",
};

export default function ChessGame() {
  const router = useRouter();
  // useMemo so we get one persistent Chess instance across renders, not a
  // fresh game every re-render.
  const game = useMemo(() => new Chess(), []);
  const [fen, setFen] = useState(game.fen());
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [hint, setHint] = useState<HintResponse | null>(null);
  const [status, setStatus] = useState<string>("Your move.");
  const [thinking, setThinking] = useState(false);
  const [hintLoading, setHintLoading] = useState(false);

  useEffect(() => {
    api.getProfile().then(setProfile).catch((e) => setStatus(`Couldn't load profile: ${e.message}`));
  }, []);

  const endGameIfOver = useCallback(
    async (result: "user_win" | "user_loss" | "draw" | null) => {
      if (!result) return;
      setStatus(
        result === "user_win" ? "You won! 🎉" : result === "user_loss" ? "Bot wins — good fight." : "Draw."
      );
      try {
        await api.finishGame(game.pgn(), result);
      } catch (e) {
        console.error("Failed to record game result", e);
      }
    },
    [game]
  );

  const onDrop = useCallback(
    (source: string, target: string) => {
      const move = game.move({ from: source, to: target, promotion: "q" });
      if (move === null) return false; // illegal move, snap back

      setFen(game.fen());
      setHint(null);

      if (game.isGameOver()) {
        const result = game.isDraw() ? "draw" : "user_win"; // user just moved and ended it
        endGameIfOver(result);
        return true;
      }

      // Ask the backend for the bot's reply.
      setThinking(true);
      setStatus("Bot is thinking...");
      api
        .requestBotMove(game.fen())
        .then((res) => {
          game.move(res.move_uci, { sloppy: true } as any);
          setFen(game.fen());
          setStatus(res.is_check ? "Check!" : "Your move.");
          endGameIfOver(res.result);
        })
        .catch((e) => setStatus(`Error getting bot move: ${e.message}`))
        .finally(() => setThinking(false));

      return true;
    },
    [game, endGameIfOver]
  );

  const requestHint = useCallback(() => {
    setHintLoading(true);
    api
      .getHint(game.fen())
      .then(setHint)
      .catch((e) => setStatus(`Couldn't get hint: ${e.message}`))
      .finally(() => setHintLoading(false));
  }, [game]);

  return (
    <div className="game-layout">
      <div className="board-wrap">
        <Chessboard position={fen} onPieceDrop={onDrop} arePiecesDraggable={!thinking} />
      </div>

      <div className="side-panel">
        <div className="side-panel-header">
          <h1>{profile?.full_name ? `Hey, ${profile.full_name.split(" ")[0]}` : "ChessTempo"}</h1>
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
        <p className="status-line">{thinking && <span className="spinner" />}{status}</p>

        {profile && (
          <div className="stat-row">
            <span className="badge">{DIFFICULTY_LABELS[profile.starting_difficulty] ?? profile.starting_difficulty}</span>
            <span className="badge">strength {profile.strength.toFixed(2)}</span>
            <span className="badge">{profile.games_played} games played</span>
          </div>
        )}

        <button className="btn btn-secondary" onClick={requestHint} disabled={thinking || hintLoading}>
          {hintLoading && <span className="spinner" />}
          {hintLoading ? "Thinking..." : "Get a hint"}
        </button>

        {hint && (
          <div className="hint-panel">
            {hint.eval_cp !== null && <p className="hint-eval">Eval: {(hint.eval_cp / 100).toFixed(2)}</p>}
            {hint.motifs.length === 0 && <p>Nothing jumps out — solid position.</p>}
            {hint.motifs.map((m, i) => (
              <p key={i}>⚠️ {m.description}</p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
