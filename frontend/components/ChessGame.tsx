"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Chess, Square } from "chess.js";
import { Chessboard } from "react-chessboard";
import { api, HintResponse, ProfileResponse } from "@/lib/api";
import { supabase } from "@/lib/supabaseClient";

const DIFFICULTY_LABELS: Record<string, string> = {
  beginner: "Beginner",
  casual: "Casual",
  club: "Club",
  strong: "Strong",
};

const PIECE_GLYPH: Record<string, string> = {
  p: "♟",
  n: "♞",
  b: "♝",
  r: "♜",
  q: "♛",
};

const PIECE_VALUE: Record<string, number> = { p: 1, n: 3, b: 3, r: 5, q: 9 };

type GameResult = "user_win" | "user_loss" | "draw" | null;

export default function ChessGame() {
  const router = useRouter();
  // useMemo so we get one persistent Chess instance across renders, not a
  // fresh game every re-render. Bumping `gameKey` forces a fresh instance
  // for "New Game".
  const [gameKey, setGameKey] = useState(0);
  const game = useMemo(() => new Chess(), [gameKey]);

  const [fen, setFen] = useState(game.fen());
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [hint, setHint] = useState<HintResponse | null>(null);
  const [status, setStatus] = useState<string>("Your move.");
  const [thinking, setThinking] = useState(false);
  const [hintLoading, setHintLoading] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [selectedSquare, setSelectedSquare] = useState<Square | null>(null);
  const [legalTargets, setLegalTargets] = useState<Square[]>([]);
  const [history, setHistory] = useState<string[]>([]);
  const [captured, setCaptured] = useState<{ byUser: string[]; byBot: string[] }>({
    byUser: [],
    byBot: [],
  });
  const [gameOver, setGameOver] = useState<{ result: GameResult; reason: string } | null>(null);

  const loadProfile = useCallback(() => {
    setProfileError(null);
    api.getProfile().then(setProfile).catch((e) => setProfileError(e.message));
  }, []);

  useEffect(loadProfile, [loadProfile, gameKey]);

  const materialDiff = useMemo(() => {
    const userGain = captured.byUser.reduce((s, p) => s + (PIECE_VALUE[p] ?? 0), 0);
    const botGain = captured.byBot.reduce((s, p) => s + (PIECE_VALUE[p] ?? 0), 0);
    return userGain - botGain;
  }, [captured]);

  const endGameIfOver = useCallback(
    async (result: GameResult, reason: string) => {
      if (!result) return;
      setGameOver({ result, reason });
      try {
        await api.finishGame(game.pgn(), result);
        loadProfile();
      } catch (e) {
        console.error("Failed to record game result", e);
      }
    },
    [game, loadProfile]
  );

  const describeGameOver = (g: Chess): string => {
    if (g.isCheckmate()) return "Checkmate";
    if (g.isStalemate()) return "Stalemate";
    if (g.isThreefoldRepetition()) return "Draw by repetition";
    if (g.isInsufficientMaterial()) return "Draw — insufficient material";
    if (g.isDraw()) return "Draw — 50-move rule";
    return "Game over";
  };

  const applyMove = useCallback(
    (from: string, to: string): boolean => {
      const move = game.move({ from, to, promotion: "q" });
      if (move === null) return false;

      if (move.captured) {
        setCaptured((c) =>
          move.color === "w"
            ? { ...c, byUser: [...c.byUser, move.captured!] }
            : { ...c, byBot: [...c.byBot, move.captured!] }
        );
      }

      setFen(game.fen());
      setHistory(game.history());
      setHint(null);
      setSelectedSquare(null);
      setLegalTargets([]);
      return true;
    },
    [game]
  );

  const requestBotReply = useCallback(() => {
    setThinking(true);
    setStatus("Bot is thinking...");
    api
      .requestBotMove(game.fen())
      .then((res) => {
        const [from, to] = [res.move_uci.slice(0, 2), res.move_uci.slice(2, 4)];
        applyMove(from, to);
        setStatus(res.is_check ? "Check!" : "Your move.");
        if (res.is_game_over) {
          endGameIfOver(res.result, describeGameOver(game));
        }
      })
      .catch((e) => setStatus(`Error getting bot move: ${e.message}`))
      .finally(() => setThinking(false));
  }, [game, applyMove, endGameIfOver]);

  const onDrop = useCallback(
    (source: string, target: string) => {
      if (thinking || gameOver) return false;
      const ok = applyMove(source, target);
      if (!ok) return false;

      if (game.isGameOver()) {
        endGameIfOver(game.isDraw() ? "draw" : "user_win", describeGameOver(game));
        return true;
      }
      requestBotReply();
      return true;
    },
    [game, thinking, gameOver, applyMove, endGameIfOver, requestBotReply]
  );

  const onSquareClick = useCallback(
    (square: Square) => {
      if (thinking || gameOver) return;

      if (selectedSquare && legalTargets.includes(square)) {
        onDrop(selectedSquare, square);
        return;
      }

      const piece = game.get(square);
      if (piece && piece.color === game.turn()) {
        setSelectedSquare(square);
        setLegalTargets(game.moves({ square, verbose: true }).map((m) => m.to as Square));
      } else {
        setSelectedSquare(null);
        setLegalTargets([]);
      }
    },
    [game, thinking, gameOver, selectedSquare, legalTargets, onDrop]
  );

  const requestHint = useCallback(() => {
    setHintLoading(true);
    api
      .getHint(game.fen())
      .then(setHint)
      .catch((e) => setStatus(`Couldn't get hint: ${e.message}`))
      .finally(() => setHintLoading(false));
  }, [game]);

  const resign = useCallback(() => {
    if (gameOver || game.history().length === 0) return;
    endGameIfOver("user_loss", "Resigned");
  }, [game, gameOver, endGameIfOver]);

  const newGame = useCallback(() => {
    setGameKey((k) => k + 1);
    setFen(new Chess().fen());
    setHistory([]);
    setCaptured({ byUser: [], byBot: [] });
    setHint(null);
    setGameOver(null);
    setStatus("Your move.");
    setSelectedSquare(null);
    setLegalTargets([]);
  }, []);

  const squareStyles = useMemo(() => {
    const styles: Record<string, React.CSSProperties> = {};
    if (selectedSquare) {
      styles[selectedSquare] = { background: "rgba(217, 164, 65, 0.35)" };
    }
    for (const sq of legalTargets) {
      const occupied = !!game.get(sq);
      styles[sq] = {
        background: occupied
          ? "radial-gradient(circle, transparent 55%, rgba(217, 164, 65, 0.45) 58%)"
          : "radial-gradient(circle, rgba(217, 164, 65, 0.45) 18%, transparent 20%)",
      };
    }
    return styles;
  }, [selectedSquare, legalTargets, game]);

  const movePairs = useMemo(() => {
    const pairs: [string, string | undefined][] = [];
    for (let i = 0; i < history.length; i += 2) {
      pairs.push([history[i], history[i + 1]]);
    }
    return pairs;
  }, [history]);

  return (
    <div className="play-shell">
      <nav className="nav">
        <div className="nav-brand" style={{ cursor: "pointer" }} onClick={() => router.push("/")}>
          <span className="brand-mark">♞</span>
          <span className="brand-name">ChessTempo</span>
        </div>
        <button
          className="btn-link"
          onClick={async () => {
            await supabase.auth.signOut();
            router.push("/");
          }}
        >
          Log out
        </button>
      </nav>

      <div className="game-layout">
        <div className="board-column">
          <div className="player-bar">
            <span className="player-name">
              <span className="player-glyph">♞</span> ChessTempo Bot
            </span>
            <span className="captured-row">
              {captured.byBot.map((p, i) => (
                <span key={i}>{PIECE_GLYPH[p]}</span>
              ))}
              {materialDiff < 0 && <span className="material-diff">+{-materialDiff}</span>}
            </span>
          </div>

          <div className="board-wrap">
            <Chessboard
              position={fen}
              onPieceDrop={onDrop}
              onSquareClick={onSquareClick}
              customSquareStyles={squareStyles}
              arePiecesDraggable={!thinking && !gameOver}
              customBoardStyle={{ borderRadius: 0 }}
              customDarkSquareStyle={{ backgroundColor: "#8b6b4a" }}
              customLightSquareStyle={{ backgroundColor: "#eddcc0" }}
            />
            {gameOver && (
              <div className="game-over-overlay">
                <div className="game-over-card">
                  <h2>
                    {gameOver.result === "user_win" && "You won! 🎉"}
                    {gameOver.result === "user_loss" && "Bot wins"}
                    {gameOver.result === "draw" && "Draw"}
                  </h2>
                  <p>{gameOver.reason}</p>
                  <button className="btn" onClick={newGame}>
                    New game
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="player-bar">
            <span className="player-name">
              <span className="player-glyph">♟</span> {profile?.full_name?.split(" ")[0] ?? "You"}
            </span>
            <span className="captured-row">
              {captured.byUser.map((p, i) => (
                <span key={i}>{PIECE_GLYPH[p]}</span>
              ))}
              {materialDiff > 0 && <span className="material-diff">+{materialDiff}</span>}
            </span>
          </div>
        </div>

        <div className="side-panel">
          <p className="status-line">
            {thinking && <span className="spinner" />}
            {status}
          </p>

          {profileError && <p className="error-text">Couldn't load profile: {profileError}</p>}

          {profile && (
            <div className="stat-row">
              <span className="badge">
                {DIFFICULTY_LABELS[profile.starting_difficulty] ?? profile.starting_difficulty}
              </span>
              <span className="badge">strength {profile.strength.toFixed(2)}</span>
              <span className="badge">{profile.games_played} games played</span>
            </div>
          )}

          <div className="action-row">
            <button className="btn btn-secondary" onClick={requestHint} disabled={thinking || hintLoading || !!gameOver}>
              {hintLoading ? "Thinking..." : "Get a hint"}
            </button>
            <button className="btn btn-secondary" onClick={resign} disabled={thinking || !!gameOver || history.length === 0}>
              Resign
            </button>
            <button className="btn btn-secondary" onClick={newGame}>
              New game
            </button>
          </div>

          {hint && (
            <div className="hint-panel">
              {hint.eval_cp !== null && <p className="hint-eval">Eval: {(hint.eval_cp / 100).toFixed(2)}</p>}
              {hint.motifs.length === 0 && <p>Nothing jumps out — solid position.</p>}
              {hint.motifs.map((m, i) => (
                <p key={i}>⚠️ {m.description}</p>
              ))}
            </div>
          )}

          <div className="move-list">
            <h3>Moves</h3>
            {movePairs.length === 0 && <p className="hint-eval">No moves yet.</p>}
            {movePairs.map(([white, black], i) => (
              <div className="move-row" key={i}>
                <span className="move-num">{i + 1}.</span>
                <span className="move-san">{white}</span>
                <span className="move-san">{black ?? ""}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
