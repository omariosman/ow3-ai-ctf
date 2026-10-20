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

// ---- Release Roulette ----

export interface ReleaseView {
  release_id: string;
  project: string;
  version: string;
  environment: string;
  status: string;
  protected: boolean;
  last_actor: string | null;
}

export interface AuditEvent {
  request_id: string;
  tool: string;
  release_id: string | null;
  actor: string;
  ok: boolean;
  transition: string | null;
  timestamp: string;
}

export interface ToolCall {
  tool: string;
  release_id: string | null;
  ok: boolean;
  transition: string | null;
}

export interface SecurityAnalysis {
  owasp: string;
  root_cause: string;
  what_happened: string[];
  broken: string;
  secure: string;
}

export interface ReleaseRouletteState {
  status: string;
  target_release: string;
  releases: ReleaseView[];
  audit: AuditEvent[];
  challenge_solved: boolean;
  analysis: SecurityAnalysis | null;
}

export interface ReleaseRouletteChatResponse {
  request_id: string;
  reply: string;
  tool_calls: ToolCall[];
  state: ReleaseRouletteState;
  solved_condition: boolean;
  flag: string | null;
  note: string | null;
}

const RR_BASE = `${API_BASE}/api/challenges/release-roulette`;

export async function releaseRouletteState(
  playerId: string
): Promise<ReleaseRouletteState> {
  const res = await fetch(
    `${RR_BASE}/state?player_id=${encodeURIComponent(playerId)}`,
    { cache: "no-store" }
  );
  return handle<ReleaseRouletteState>(res);
}

export async function releaseRouletteChat(
  message: string,
  playerId: string
): Promise<ReleaseRouletteChatResponse> {
  const res = await fetch(`${RR_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, player_id: playerId }),
  });
  return handle<ReleaseRouletteChatResponse>(res);
}

export async function releaseRouletteReset(
  playerId: string
): Promise<ReleaseRouletteState> {
  const res = await fetch(`${RR_BASE}/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_id: playerId }),
  });
  return handle<ReleaseRouletteState>(res);
}

// ---------------------------------------------------------------------------
// RenderTrap
// ---------------------------------------------------------------------------

export interface RenderTrapTicket {
  id: string;
  customer: string;
  subject: string;
  priority: string;
  body: string;
}

export interface RenderTrapState {
  status: string;
  ticket: RenderTrapTicket;
  max_note_length: number;
  note: string;
  raw_output: string | null;
  generation: number;
  preview_html: string | null;
  challenge_solved: boolean;
  analysis: SecurityAnalysis | null;
}

export interface RenderTrapProofResponse {
  accepted: boolean;
  reason: string | null;
  flag: string | null;
  state: RenderTrapState;
}

const RT_BASE = `${API_BASE}/api/challenges/render-trap`;

export async function renderTrapState(playerId: string): Promise<RenderTrapState> {
  const res = await fetch(`${RT_BASE}/state?player_id=${encodeURIComponent(playerId)}`, {
    cache: "no-store",
  });
  return handle<RenderTrapState>(res);
}

export async function renderTrapSummarize(
  note: string,
  playerId: string
): Promise<RenderTrapState> {
  const res = await fetch(`${RT_BASE}/summarize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note, player_id: playerId }),
  });
  return handle<RenderTrapState>(res);
}

export async function renderTrapProof(
  generation: number,
  nonce: string,
  playerId: string
): Promise<RenderTrapProofResponse> {
  const res = await fetch(`${RT_BASE}/proof`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      event: "render_execution_confirmed",
      generation,
      nonce,
      player_id: playerId,
    }),
  });
  return handle<RenderTrapProofResponse>(res);
}

export async function renderTrapReset(playerId: string): Promise<RenderTrapState> {
  const res = await fetch(`${RT_BASE}/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_id: playerId }),
  });
  return handle<RenderTrapState>(res);
}

// ---------------------------------------------------------------------------
// Model Crate
// ---------------------------------------------------------------------------

export interface ModelCrateTrustedRelease {
  component: string;
  version: string;
  artifact_id: string;
  expected_sha256: string;
  source_repository: string;
  approved_signers: string[];
  signature_required: boolean;
  approver: string;
  approved_on: string;
}

export interface ModelCratePackageManifest {
  name: string;
  version: string;
  artifact_id: string;
  publisher: string;
  claimed_sha256: string;
  attestation: {
    signer: string;
    source_repository: string;
    signed_sha256: string;
    build_id: string;
  };
}

export interface ModelCrateState {
  status: "UNVERIFIED" | "INSPECTED" | "MISMATCH_CONFIRMED" | "QUARANTINED";
  incident: string;
  inventory: {
    component: string;
    version: string;
    artifact_id: string;
    publisher: string;
    status: string;
  };
  trusted_release: ModelCrateTrustedRelease;
  package_manifest: ModelCratePackageManifest;
  artifact: {
    artifact_id: string;
    size_bytes: number;
    actual_sha256: string;
    claimed_version: string;
  } | null;
  comparison: {
    expected_sha256: string;
    actual_sha256: string;
    claimed_sha256: string;
    digest_match: boolean;
    claimed_matches_trusted: boolean;
  } | null;
  provenance: {
    simulated: boolean;
    verified: boolean;
    checks: { name: string; passed: boolean; detail: string }[];
  } | null;
  loaded: boolean;
  consequence: {
    tampered: boolean;
    summary: string;
    samples: { ticket: string; label: string; expected_route: string; actual_route: string }[];
  } | null;
  audit: { seq: number; event: string; detail: string }[];
  challenge_solved: boolean;
  analysis: SecurityAnalysis | null;
}

export interface ModelCrateActionResponse {
  message: string;
  changed: boolean;
  flag: string | null;
  state: ModelCrateState;
}

export type ModelCrateAction =
  | "inspect"
  | "compare"
  | "provenance"
  | "load"
  | "quarantine";

const MC_BASE = `${API_BASE}/api/challenges/model-crate`;

export async function modelCrateState(playerId: string): Promise<ModelCrateState> {
  const res = await fetch(`${MC_BASE}/state?player_id=${encodeURIComponent(playerId)}`, {
    cache: "no-store",
  });
  return handle<ModelCrateState>(res);
}

export async function modelCrateAction(
  action: ModelCrateAction,
  playerId: string
): Promise<ModelCrateActionResponse> {
  const res = await fetch(`${MC_BASE}/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_id: playerId }),
  });
  return handle<ModelCrateActionResponse>(res);
}

export async function modelCrateReset(playerId: string): Promise<ModelCrateState> {
  const res = await fetch(`${MC_BASE}/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_id: playerId }),
  });
  return handle<ModelCrateState>(res);
}

// ---------------------------------------------------------------------------
// Context Hijack
// ---------------------------------------------------------------------------

export interface ContextHijackDocument {
  doc_id: string;
  title: string;
  source: string;
  trusted: boolean;
  content: string;
}

export interface ContextHijackSource {
  doc_id: string;
  title: string;
  trusted: boolean;
}

export interface ContextHijackState {
  status: string;
  max_query_length: number;
  documents: ContextHijackDocument[];
  query: string;
  response: string | null;
  sources: ContextHijackSource[];
  challenge_solved: boolean;
  analysis: SecurityAnalysis | null;
}

export interface ContextHijackAskResponse {
  solved_condition: boolean;
  flag: string | null;
  state: ContextHijackState;
}

const CH_BASE = `${API_BASE}/api/challenges/context-hijack`;

export async function contextHijackState(playerId: string): Promise<ContextHijackState> {
  const res = await fetch(`${CH_BASE}/state?player_id=${encodeURIComponent(playerId)}`, {
    cache: "no-store",
  });
  return handle<ContextHijackState>(res);
}

export async function contextHijackAsk(
  query: string,
  playerId: string
): Promise<ContextHijackAskResponse> {
  const res = await fetch(`${CH_BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, player_id: playerId }),
  });
  return handle<ContextHijackAskResponse>(res);
}

export async function contextHijackReset(playerId: string): Promise<ContextHijackState> {
  const res = await fetch(`${CH_BASE}/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_id: playerId }),
  });
  return handle<ContextHijackState>(res);
}

// ---------------------------------------------------------------------------
// Trace Leak
// ---------------------------------------------------------------------------

export interface TraceLeakState {
  status: string;
  max_question_length: number;
  sample_questions: string[];
  question: string;
  response: string | null;
  challenge_solved: boolean;
  analysis: SecurityAnalysis | null;
}

export interface TraceLeakTrace {
  request_id: string;
  selected_faq: string | null;
  response_mode: string;
  internal_prompt: string;
}

export interface TraceLeakEvidenceResponse {
  solved_condition: boolean;
  flag: string | null;
  state: TraceLeakState;
}

const TL_BASE = `${API_BASE}/api/challenges/trace-leak`;

async function tlPost<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const res = await fetch(`${TL_BASE}/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handle<T>(res);
}

export async function traceLeakState(playerId: string): Promise<TraceLeakState> {
  const res = await fetch(`${TL_BASE}/state?player_id=${encodeURIComponent(playerId)}`, {
    cache: "no-store",
  });
  return handle<TraceLeakState>(res);
}

export function traceLeakAsk(question: string, playerId: string): Promise<TraceLeakState> {
  return tlPost<TraceLeakState>("ask", { question, player_id: playerId });
}

export function traceLeakTrace(
  playerId: string
): Promise<{ trace: TraceLeakTrace; state: TraceLeakState }> {
  return tlPost("trace", { player_id: playerId });
}

export function traceLeakEvidence(
  canary: string,
  playerId: string
): Promise<TraceLeakEvidenceResponse> {
  return tlPost<TraceLeakEvidenceResponse>("evidence", { canary, player_id: playerId });
}

export function traceLeakReset(playerId: string): Promise<TraceLeakState> {
  return tlPost<TraceLeakState>("reset", { player_id: playerId });
}
