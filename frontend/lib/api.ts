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
}

export interface ProfileResponse {
  starting_difficulty: string;
  strength: number;
  games_played: number;
}

export const api = {
  getProfile: (): Promise<ProfileResponse> => authedFetch("/profile"),

  requestBotMove: (fen: string): Promise<MoveResponse> =>
    authedFetch("/game/move", { method: "POST", body: JSON.stringify({ fen }) }),

  getHint: (fen: string): Promise<HintResponse> =>
    authedFetch("/game/hint", { method: "POST", body: JSON.stringify({ fen }) }),

  finishGame: (pgn: string, result: "user_win" | "user_loss" | "draw") =>
    authedFetch("/game/finish", { method: "POST", body: JSON.stringify({ pgn, result }) }),
};
