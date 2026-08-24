"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import { api, HintResponse, ProfileResponse } from "@/lib/api";

export default function ChessGame() {
  // useMemo so we get one persistent Chess instance across renders, not a
  // fresh game every re-render.
  const game = useMemo(() => new Chess(), []);
  const [fen, setFen] = useState(game.fen());
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [hint, setHint] = useState<HintResponse | null>(null);
  const [status, setStatus] = useState<string>("Your move.");
  const [thinking, setThinking] = useState(false);

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
    api.getHint(game.fen()).then(setHint).catch((e) => setStatus(`Couldn't get hint: ${e.message}`));
  }, [game]);

  return (
    <div style={{ display: "flex", gap: 24, padding: 24, flexWrap: "wrap" }}>
      <div style={{ width: 420, maxWidth: "90vw" }}>
        <Chessboard position={fen} onPieceDrop={onDrop} arePiecesDraggable={!thinking} />
      </div>

      <div style={{ minWidth: 240 }}>
        <h2>ChessTempo</h2>
        <p>{status}</p>

        {profile && (
          <p>
            Difficulty: {profile.starting_difficulty} (strength {profile.strength.toFixed(2)}) ·{" "}
            {profile.games_played} games played
          </p>
        )}

        <button onClick={requestHint} disabled={thinking}>
          Get a hint
        </button>

        {hint && (
          <div style={{ marginTop: 12 }}>
            {hint.eval_cp !== null && <p>Eval: {(hint.eval_cp / 100).toFixed(2)}</p>}
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
