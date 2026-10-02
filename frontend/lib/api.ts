// API client for the CTF backend.
// The base URL is configurable so the same build works for local dev and Docker.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

// Single-user MVP: a stable local player id (plan section 9). Persisted in the
// browser so solves survive reloads. No authentication is needed for the MVP.
export function getPlayerId(): string {
  if (typeof window === "undefined") return "local-player";
  try {
    let id = window.localStorage.getItem("ctf_player_id");
    if (!id) {
      id = "local-player";
      window.localStorage.setItem("ctf_player_id", id);
    }
    return id;
  } catch {
    return "local-player";
  }
}

export interface ChallengeSummary {
  slug: string;
  title: string;
  category: string;
  difficulty: string;
  points: number;
  author: string;
  solved: boolean;
}

export interface Hint {
  order: number;
  cost: number;
  text: string;
}

export interface ChallengeDetail extends ChallengeSummary {
  description: string;
  learning_objectives: string[];
  hints: Hint[];
  unlocked: boolean;
}

export interface PredictResponse {
  label: string;
  confidence: number;
  probabilities: Record<string, number>;
  request_number: number;
  solved_condition: boolean;
  flag: string | null;
  note: string | null;
}

export interface SubmitResponse {
  correct: boolean;
  solved: boolean;
  message: string;
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function listChallenges(playerId: string): Promise<ChallengeSummary[]> {
  const res = await fetch(
    `${API_BASE}/api/challenges?player_id=${encodeURIComponent(playerId)}`,
    { cache: "no-store" }
  );
  return handle<ChallengeSummary[]>(res);
}

export async function getChallenge(
  slug: string,
  playerId: string
): Promise<ChallengeDetail> {
  const res = await fetch(
    `${API_BASE}/api/challenges/${slug}?player_id=${encodeURIComponent(playerId)}`,
    { cache: "no-store" }
  );
  return handle<ChallengeDetail>(res);
}

export async function predict(
  slug: string,
  text: string,
  playerId: string
): Promise<PredictResponse> {
  const res = await fetch(`${API_BASE}/api/challenges/${slug}/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, player_id: playerId }),
  });
  return handle<PredictResponse>(res);
}

export async function submitFlag(
  slug: string,
  flag: string,
  playerId: string
): Promise<SubmitResponse> {
  const res = await fetch(`${API_BASE}/api/challenges/${slug}/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ flag, player_id: playerId }),
  });
  return handle<SubmitResponse>(res);
}
