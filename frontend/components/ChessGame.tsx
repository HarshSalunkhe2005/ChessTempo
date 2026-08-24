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

const FIGURINE: Record<string, string> = { N: "♞", B: "♝", R: "♜", Q: "♛", K: "♚" };

/** SAN like "Nf3" -> "♞f3" — figurine notation, as used in most move lists. */
function toFigurine(san: string): string {
  const glyph = FIGURINE[san[0]];
  return glyph ? glyph + san.slice(1) : san;
}

/** Maps our 0-1 difficulty "strength" to a familiar chess-rating-looking
 * number, purely cosmetic — there's no real rating system underneath yet. */
function strengthToRating(strength: number): number {
  return Math.round(400 + strength * 2000);
}

function initials(name: string): string {
  return name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

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

  const rating = useMemo(() => strengthToRating(profile?.strength ?? 0.3), [profile]);
  const whiteToMove = fen.split(" ")[1] === "w";

  // Eval bar fill, from White's perspective regardless of whose turn it
  // is — hint.eval_cp is from the side-to-move's perspective, and hint is
  // always cleared on the next move, so game.turn() here still matches
  // the position the hint was fetched for.
  const evalPercent = useMemo(() => {
    if (hint?.eval_cp == null) return 50;
    const whiteCp = game.turn() === "w" ? hint.eval_cp : -hint.eval_cp;
    const clamped = Math.max(-1000, Math.min(1000, whiteCp));
    return 50 + (clamped / 1000) * 50;
  }, [hint, game]);

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
            <span className="avatar avatar-bot">♞</span>
            <span className="player-info">
              <span className="player-name">
                ChessTempo Bot<span className="rating">({rating})</span>
              </span>
              <span className="captured-row">
                {captured.byBot.map((p, i) => (
                  <span key={i} style={{ marginInlineStart: i === 0 ? 0 : -10 }}>
                    {PIECE_GLYPH[p]}
                  </span>
                ))}
                {materialDiff < 0 && <span className="material-diff">+{-materialDiff}</span>}
              </span>
            </span>
            <span className={`clock-pill${!whiteToMove && !gameOver ? " clock-active" : ""}`}>∞</span>
          </div>

          <div className="board-with-eval">
            <div className="eval-bar" title={hint?.eval_cp != null ? `Eval: ${(hint.eval_cp / 100).toFixed(2)}` : "Request a hint to see the eval"}>
              <div className="eval-bar-fill" style={{ height: `${evalPercent}%` }} />
            </div>

            <div className="board-wrap">
              <Chessboard
                position={fen}
                onPieceDrop={onDrop}
                onSquareClick={onSquareClick}
                customSquareStyles={squareStyles}
                arePiecesDraggable={!thinking && !gameOver}
                customBoardStyle={{ borderRadius: 0 }}
                // The classic brown board theme shared by lichess and
                // chess.com — #f0d9b5 / #946f51 is the industry-standard
                // pairing, not an approximation.
                customDarkSquareStyle={{ backgroundColor: "#946f51" }}
                customLightSquareStyle={{ backgroundColor: "#f0d9b5" }}
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
          </div>

          <div className="player-bar">
            <span className="avatar avatar-user">{initials(profile?.full_name || "You")}</span>
            <span className="player-info">
              <span className="player-name">
                {profile?.full_name?.split(" ")[0] ?? "You"}
                <span className="rating">({rating})</span>
              </span>
              <span className="captured-row">
                {captured.byUser.map((p, i) => (
                  <span key={i} style={{ marginInlineStart: i === 0 ? 0 : -10 }}>
                    {PIECE_GLYPH[p]}
                  </span>
                ))}
                {materialDiff > 0 && <span className="material-diff">+{materialDiff}</span>}
              </span>
            </span>
            <span className={`clock-pill${whiteToMove && !gameOver ? " clock-active" : ""}`}>∞</span>
          </div>
        </div>

        <div className="side-panel">
          <div className="panel-card">
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
                <span className="badge">{profile.games_played} games played</span>
              </div>
            )}

            <div className="action-row">
              <button className="btn btn-secondary" onClick={requestHint} disabled={thinking || hintLoading || !!gameOver}>
                {hintLoading ? "Thinking..." : "💡 Hint"}
              </button>
              <button className="btn btn-secondary" onClick={resign} disabled={thinking || !!gameOver || history.length === 0}>
                🏳 Resign
              </button>
              <button className="btn btn-secondary" onClick={newGame}>
                ↻ New game
              </button>
            </div>
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
                <span className="move-san">{toFigurine(white)}</span>
                <span className="move-san">{black ? toFigurine(black) : ""}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
