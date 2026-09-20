"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Chess, Square } from "chess.js";
import { Chessboard } from "react-chessboard";
import { api, HintResponse, ProfileResponse, ReviewResponse } from "@/lib/api";
import { supabase } from "@/lib/supabaseClient";
import { DIFFICULTY_LABELS, toFigurine, strengthToRating, initials, CLASSIFICATION_COLOR } from "@/lib/chessDisplay";
import { takeReviewHandoff } from "@/lib/reviewHandoff";

const PIECE_GLYPH: Record<string, string> = {
  p: "♟",
  n: "♞",
  b: "♝",
  r: "♜",
  q: "♛",
};

const PIECE_VALUE: Record<string, number> = { p: 1, n: 3, b: 3, r: 5, q: 9 };

type GameResult = "user_win" | "user_loss" | "draw" | null;

// Stroke-based icons, not emoji — keeps the action row consistent with the
// rest of the brand rather than relying on OS emoji rendering.
function IconHint() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path
        d="M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.6.55 1 1.3 1 2.1V16h6v-.4c0-.8.4-1.55 1-2.1A6 6 0 0 0 12 3z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconFlag() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path
        d="M6 3v18M6 4h11l-2.5 3.5L17 11H6"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconRefresh() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path
        d="M4 12a8 8 0 1 1 2.6 5.9M4 12V7m0 5h5"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconInfo() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0, opacity: 0.7 }}>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" />
      <path d="M12 8v5M12 16h.01" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

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
  const [lastMove, setLastMove] = useState<{ from: Square; to: Square } | null>(null);
  const [history, setHistory] = useState<string[]>([]);
  const [captured, setCaptured] = useState<{ byUser: string[]; byBot: string[] }>({
    byUser: [],
    byBot: [],
  });
  const [gameOver, setGameOver] = useState<{ result: GameResult; reason: string } | null>(null);
  const [review, setReview] = useState<ReviewResponse | null>(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);
  // null = showing the live/final board; a number = navigating the
  // reviewed game ply-by-ply (0 = starting position).
  const [reviewPly, setReviewPly] = useState<number | null>(null);
  // Eval for the *current live position*, refreshed automatically after
  // every move (not just when the user asks for a Hint) so the eval bar
  // actually tracks the game instead of sitting frozen between hints.
  const [boardEval, setBoardEval] = useState<number | null>(null);

  const loadProfile = useCallback(() => {
    setProfileError(null);
    api.getProfile().then(setProfile).catch((e) => setProfileError(e.message));
  }, []);

  useEffect(loadProfile, [loadProfile, gameKey]);

  const refreshBoardEval = useCallback((fenToEval: string) => {
    api
      .getHint(fenToEval)
      .then((res) => setBoardEval(res.eval_cp))
      .catch(() => {
        /* the eval bar just stays at its last value — not worth surfacing an error for */
      });
  }, []);

  // Keep the bar honest for a fresh board too, not just after moves.
  useEffect(() => {
    refreshBoardEval(new Chess().fen());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameKey]);

  // Arriving here from a past-game click on the profile page: load that
  // game's PGN into the board and drop straight into review, instead of
  // starting a fresh game. Runs once on mount — a ref guard rather than
  // an empty dependency array's usual caveats, since this also has to
  // survive React StrictMode's double-invoke in development.
  const didLoadHandoff = useRef(false);
  useEffect(() => {
    if (didLoadHandoff.current) return;
    didLoadHandoff.current = true;

    const handoff = takeReviewHandoff();
    if (!handoff) return;

    try {
      game.loadPgn(handoff.pgn);
    } catch {
      return; // unexpected PGN shape — fall through to the normal fresh game
    }

    const byUser: string[] = [];
    const byBot: string[] = [];
    for (const m of game.history({ verbose: true })) {
      if (!m.captured) continue;
      (m.color === "w" ? byUser : byBot).push(m.captured);
    }

    setFen(game.fen());
    setHistory(game.history());
    setCaptured({ byUser, byBot });
    setGameOver({ result: handoff.result, reason: "From your game history" });
    setStatus("Game over");

    setReviewLoading(true);
    api
      .reviewGame(handoff.pgn)
      .then((res) => {
        setReview(res);
        setReviewPly(0);
      })
      .catch((e) => setReviewError(e.message))
      .finally(() => setReviewLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
      setLastMove({ from: move.from as Square, to: move.to as Square });
      refreshBoardEval(game.fen());
      return true;
    },
    [game, refreshBoardEval]
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
      .then((res) => {
        setHint(res);
        setBoardEval(res.eval_cp); // already fresh from refreshBoardEval, but no reason to disagree
      })
      .catch((e) => setStatus(`Couldn't get hint: ${e.message}`))
      .finally(() => setHintLoading(false));
  }, [game]);

  const resign = useCallback(() => {
    if (gameOver || game.history().length === 0) return;
    endGameIfOver("user_loss", "Resigned");
  }, [game, gameOver, endGameIfOver]);

  const requestReview = useCallback(() => {
    setReviewError(null);
    setReviewLoading(true);
    api
      .reviewGame(game.pgn())
      .then((res) => {
        setReview(res);
        setReviewPly(0); // drop straight into move-by-move navigation, starting from the opening
      })
      .catch((e) => setReviewError(e.message))
      .finally(() => setReviewLoading(false));
  }, [game]);

  // Every position the reviewed game passed through, so clicking a move
  // (or paging Prev/Next) can show the actual board at that point rather
  // than just a classification tag next to the SAN.
  const reviewFens = useMemo(() => {
    if (!review) return [];
    const replay = new Chess();
    const fens = [replay.fen()];
    for (const m of review.moves) {
      try {
        replay.move(m.san);
      } catch {
        // A SAN the reviewed PGN itself produced should always replay
        // cleanly; if it somehow doesn't, stop rather than show a wrong
        // board for every ply after.
        break;
      }
      fens.push(replay.fen());
    }
    return fens;
  }, [review]);

  const exitReview = useCallback(() => setReviewPly(null), []);
  const stepReview = useCallback(
    (delta: number) => {
      setReviewPly((p) => {
        if (p === null || reviewFens.length === 0) return p;
        return Math.max(0, Math.min(reviewFens.length - 1, p + delta));
      });
    },
    [reviewFens.length]
  );

  const newGame = useCallback(() => {
    setGameKey((k) => k + 1);
    setFen(new Chess().fen());
    setHistory([]);
    setCaptured({ byUser: [], byBot: [] });
    setHint(null);
    setBoardEval(null);
    setGameOver(null);
    setStatus("Your move.");
    setSelectedSquare(null);
    setLegalTargets([]);
    setLastMove(null);
    setReview(null);
    setReviewError(null);
    setReviewPly(null);
  }, []);

  const squareStyles = useMemo(() => {
    const styles: Record<string, React.CSSProperties> = {};
    if (lastMove) {
      const lastMoveStyle = { background: "rgba(217, 164, 65, 0.28)" };
      styles[lastMove.from] = lastMoveStyle;
      styles[lastMove.to] = lastMoveStyle;
    }
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
  }, [selectedSquare, legalTargets, lastMove, game]);

  const rating = useMemo(() => strengthToRating(profile?.strength ?? 0.3), [profile]);
  const reviewing = reviewPly !== null && review !== null;
  const displayedFen = reviewing ? reviewFens[reviewPly] ?? fen : fen;
  const whiteToMove = displayedFen.split(" ")[1] === "w";

  // Eval bar fill, from White's perspective regardless of whose turn it
  // is. Two sources depending on mode: `review.moves[].eval_cp` (already
  // White's-perspective, per tempo.mentor.review) while paging through a
  // finished game, or the live `boardEval` (side-to-move's perspective,
  // refreshed after every move — see refreshBoardEval) otherwise.
  const evalPercent = useMemo(() => {
    let whiteCp: number | null = null;
    if (reviewing) {
      whiteCp = reviewPly === 0 ? 0 : review!.moves[reviewPly - 1]?.eval_cp ?? null;
    } else if (boardEval != null) {
      whiteCp = game.turn() === "w" ? boardEval : -boardEval;
    }
    if (whiteCp == null) return 50;
    const clamped = Math.max(-1000, Math.min(1000, whiteCp));
    return 50 + (clamped / 1000) * 50;
  }, [reviewing, reviewPly, review, boardEval, game]);

  const movePairs = useMemo(() => {
    const pairs: [string, string | undefined][] = [];
    for (let i = 0; i < history.length; i += 2) {
      pairs.push([history[i], history[i + 1]]);
    }
    return pairs;
  }, [history]);

  const classificationByPly = useMemo(() => {
    const map = new Map<number, string>();
    review?.moves.forEach((m) => map.set(m.ply, m.classification));
    return map;
  }, [review]);

  const currentReviewMove = reviewing && reviewPly! > 0 ? review!.moves[reviewPly! - 1] : null;

  return (
    <div className="play-shell">
      <nav className="nav">
        <div className="nav-brand" style={{ cursor: "pointer" }} onClick={() => router.push("/")}>
          <span className="brand-mark">♞</span>
          <span className="brand-name">ChessTempo</span>
        </div>
        <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
          <button className="btn-link" onClick={() => router.push("/profile")}>
            Profile
          </button>
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
            <div
              className="eval-bar"
              title={
                reviewing
                  ? currentReviewMove?.eval_cp != null
                    ? `Eval: ${(currentReviewMove.eval_cp / 100).toFixed(2)}`
                    : "Eval unavailable for this move"
                  : boardEval != null
                    ? `Eval: ${(boardEval / 100).toFixed(2)}`
                    : "Evaluating..."
              }
            >
              <div className="eval-bar-fill" style={{ height: `${evalPercent}%` }} />
            </div>

            <div className="board-wrap">
              <Chessboard
                position={displayedFen}
                onPieceDrop={onDrop}
                onSquareClick={onSquareClick}
                customSquareStyles={reviewing ? {} : squareStyles}
                arePiecesDraggable={!thinking && !gameOver && !reviewing}
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
                    <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
                      {!review && (
                        <button
                          className="btn btn-secondary"
                          style={{ width: "auto" }}
                          onClick={requestReview}
                          disabled={reviewLoading}
                        >
                          {reviewLoading ? "Reviewing..." : "Review game"}
                        </button>
                      )}
                      <button className="btn" style={{ width: "auto", padding: "10px 24px" }} onClick={newGame}>
                        New game
                      </button>
                    </div>
                    {reviewError && <p className="error-text">{reviewError}</p>}
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
            <div className="status-eyebrow">Game status</div>
            <p className="status-line">
              {thinking && <span className="spinner" />}
              {status}
            </p>

            {profileError && <p className="error-text">Couldn't load profile: {profileError}</p>}

            {profile && (
              <div className="stat-row">
                <span className="badge badge-accent">
                  {DIFFICULTY_LABELS[profile.starting_difficulty] ?? profile.starting_difficulty}
                </span>
                <span className="badge">{profile.games_played} games played</span>
              </div>
            )}

            <div className="action-row">
              <button className="btn btn-hint" onClick={requestHint} disabled={thinking || hintLoading || !!gameOver}>
                <IconHint />
                {hintLoading ? "Thinking..." : "Hint"}
              </button>
              <button className="btn btn-secondary" onClick={resign} disabled={thinking || !!gameOver || history.length === 0}>
                <IconFlag />
                Resign
              </button>
              <button className="btn btn-secondary" onClick={newGame}>
                <IconRefresh />
                New game
              </button>
            </div>
          </div>

          {hint ? (
            <div className="hint-panel">
              {hint.eval_label && <p className="hint-eval">{hint.eval_label}</p>}
              {hint.eval_cp !== null && <p className="hint-eval">Eval: {(hint.eval_cp / 100).toFixed(2)}</p>}
              {hint.motifs.length === 0 && <p>Nothing jumps out — solid position.</p>}
              {hint.motifs.map((m, i) => (
                <p key={i}>⚠️ {m.description}</p>
              ))}
            </div>
          ) : (
            <div className="tip-panel">
              <IconInfo />
              Request a hint any time to see the position eval and any tactics worth noticing.
            </div>
          )}

          {review && (
            <div className="panel-card" style={{ marginBottom: 0 }}>
              <div className="status-eyebrow">Accuracy</div>
              <div style={{ display: "flex", gap: 20, marginBottom: reviewing ? 16 : 0 }}>
                <div>
                  <div style={{ fontSize: 22, fontWeight: 700, fontFamily: "var(--font-display)" }}>
                    {review.accuracy_white ?? "—"}
                    {review.accuracy_white != null && "%"}
                  </div>
                  <div className="hint-eval">White</div>
                </div>
                <div>
                  <div style={{ fontSize: 22, fontWeight: 700, fontFamily: "var(--font-display)" }}>
                    {review.accuracy_black ?? "—"}
                    {review.accuracy_black != null && "%"}
                  </div>
                  <div className="hint-eval">Black</div>
                </div>
              </div>

              {reviewing && (
                <div className="review-nav">
                  <div className="review-nav-controls">
                    <button
                      className="btn btn-secondary"
                      style={{ width: "auto", padding: "6px 10px" }}
                      onClick={() => stepReview(-1)}
                      disabled={reviewPly === 0}
                    >
                      ←
                    </button>
                    <span className="hint-eval">
                      {reviewPly === 0
                        ? "Starting position"
                        : `Move ${reviewPly} of ${review.moves.length}`}
                    </span>
                    <button
                      className="btn btn-secondary"
                      style={{ width: "auto", padding: "6px 10px" }}
                      onClick={() => stepReview(1)}
                      disabled={reviewPly === reviewFens.length - 1}
                    >
                      →
                    </button>
                  </div>
                  {currentReviewMove && (
                    <p className="review-move-detail">
                      <strong>{toFigurine(currentReviewMove.san)}</strong>
                      {" — "}
                      <span style={{ color: CLASSIFICATION_COLOR[currentReviewMove.classification] }}>
                        {currentReviewMove.classification}
                      </span>
                      {currentReviewMove.eval_cp != null && (
                        <span className="hint-eval"> · eval {(currentReviewMove.eval_cp / 100).toFixed(2)}</span>
                      )}
                    </p>
                  )}
                  <button className="btn-link" onClick={exitReview} style={{ fontSize: 13 }}>
                    Back to final position
                  </button>
                </div>
              )}
            </div>
          )}

          <div className="move-list">
            <h3>Moves</h3>
            <div className="move-list-body">
              {movePairs.length === 0 && <p className="hint-eval">No moves yet.</p>}
              {movePairs.map(([white, black], i) => {
                const whitePly = i * 2 + 1;
                const blackPly = i * 2 + 2;
                const whiteClass = classificationByPly.get(whitePly);
                const blackClass = black ? classificationByPly.get(blackPly) : undefined;
                return (
                  <div className="move-row" key={i}>
                    <span className="move-num">{i + 1}.</span>
                    <span
                      className={`move-san${review ? " move-san-clickable" : ""}${reviewPly === whitePly ? " move-san-active" : ""}`}
                      onClick={review ? () => setReviewPly(whitePly) : undefined}
                    >
                      {toFigurine(white)}
                      {whiteClass && (
                        <span className="move-tag" style={{ color: CLASSIFICATION_COLOR[whiteClass] }} title={whiteClass}>
                          {whiteClass}
                        </span>
                      )}
                    </span>
                    <span
                      className={`move-san${review && black ? " move-san-clickable" : ""}${reviewPly === blackPly ? " move-san-active" : ""}`}
                      onClick={review && black ? () => setReviewPly(blackPly) : undefined}
                    >
                      {black ? toFigurine(black) : ""}
                      {blackClass && (
                        <span className="move-tag" style={{ color: CLASSIFICATION_COLOR[blackClass] }} title={blackClass}>
                          {blackClass}
                        </span>
                      )}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
