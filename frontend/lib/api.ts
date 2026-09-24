import { supabase } from "./supabaseClient";

const API_URL = process.env.NEXT_PUBLIC_API_URL!;

async function authedFetch(path: string, options: RequestInit = {}) {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    throw new Error("Not logged in");
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.access_token}`,
      ...options.headers,
    },
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json();
}

export interface MoveResponse {
  move_uci: string;
  fen_after: string;
  is_check: boolean;
  is_game_over: boolean;
  result: "user_win" | "user_loss" | "draw" | null;
}

export interface Motif {
  name: string;
  square: string;
  description: string;
}

export interface HintResponse {
  motifs: Motif[];
  eval_cp: number | null;
  eval_label: string | null;
}

export interface ProfileResponse {
  starting_difficulty: string;
  strength: number;
  games_played: number;
  full_name: string | null;
}

export interface GameSummary {
  id: string;
  result: "user_win" | "user_loss" | "draw";
  strength_at_start: number;
  strength_at_end: number;
  created_at: string;
  pgn: string;
}

export interface ProfileStats {
  total_games: number;
  wins: number;
  losses: number;
  draws: number;
  win_rate: number | null;
  current_strength: number;
}

export interface MoveReviewItem {
  ply: number;
  san: string;
  color: "white" | "black";
  classification: string;
  eval_cp: number | null;
}

export interface OpeningStat {
  name: string;
  games: number;
  wins: number;
  draws: number;
  losses: number;
}

export interface ProfileInsights {
  streak: {
    current_result: "user_win" | "user_loss" | "draw" | null;
    current_length: number;
    best_win_streak: number;
  };
  avg_moves_per_game: number | null;
  openings: OpeningStat[];
  personalization: {
    last_finetuned_at: string | null;
    games_until_next_tune: number;
    model_active: boolean;
  };
}

export interface ReviewResponse {
  moves: MoveReviewItem[];
  accuracy_white: number | null;
  accuracy_black: number | null;
}

export const api = {
  getProfile: (): Promise<ProfileResponse> => authedFetch("/profile"),

  getGames: (): Promise<GameSummary[]> => authedFetch("/games"),

  getProfileStats: (): Promise<ProfileStats> => authedFetch("/profile/stats"),

  getProfileInsights: (): Promise<ProfileInsights> => authedFetch("/profile/insights"),

  updateProfile: (body: { full_name?: string; starting_difficulty?: string }): Promise<ProfileResponse> =>
    authedFetch("/profile", { method: "PATCH", body: JSON.stringify(body) }),

  deleteAccount: (): Promise<{ deleted: boolean }> => authedFetch("/profile", { method: "DELETE" }),

  requestBotMove: (fen: string): Promise<MoveResponse> =>
    authedFetch("/game/move", { method: "POST", body: JSON.stringify({ fen }) }),

  getHint: (fen: string): Promise<HintResponse> =>
    authedFetch("/game/hint", { method: "POST", body: JSON.stringify({ fen }) }),

  finishGame: (pgn: string, result: "user_win" | "user_loss" | "draw") =>
    authedFetch("/game/finish", { method: "POST", body: JSON.stringify({ pgn, result }) }),

  // Move-quality review is slow (many Stockfish calls per game) — expect
  // this to take a while on Render's free tier; the UI should show a
  // loading state, not assume this resolves quickly.
  reviewGame: (pgn: string): Promise<ReviewResponse> =>
    authedFetch("/game/review", { method: "POST", body: JSON.stringify({ pgn }) }),
};
