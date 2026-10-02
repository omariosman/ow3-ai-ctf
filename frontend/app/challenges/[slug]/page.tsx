"use client";

import { use, useEffect, useState } from "react";
import {
  getChallenge,
  getPlayerId,
  predict,
  submitFlag,
  type ChallengeDetail,
  type PredictResponse,
} from "@/lib/api";

interface HistoryItem {
  input: string;
  result: PredictResponse;
}

export default function ChallengePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = use(params);
  const [playerId, setPlayerId] = useState("local-player");
  const [challenge, setChallenge] = useState<ChallengeDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Console state
  const [text, setText] = useState("");
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [running, setRunning] = useState(false);
  const [revealedFlag, setRevealedFlag] = useState<string | null>(null);

  // Flag submission state
  const [flag, setFlag] = useState("");
  const [submitMsg, setSubmitMsg] = useState<string | null>(null);
  const [solved, setSolved] = useState(false);

  useEffect(() => {
    const pid = getPlayerId();
    setPlayerId(pid);
    getChallenge(slug, pid)
      .then((c) => {
        setChallenge(c);
        setSolved(c.solved);
      })
      .catch((e) => setError(e.message));
  }, [slug]);

  async function runPrediction() {
    if (running) return;
    setRunning(true);
    try {
      const result = await predict(slug, text, playerId);
      setHistory((h) => [{ input: text, result }, ...h].slice(0, 50));
      if (result.flag) {
        setRevealedFlag(result.flag);
        setFlag(result.flag);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }

  async function doSubmit() {
    setSubmitMsg(null);
    try {
      const r = await submitFlag(slug, flag, playerId);
      setSubmitMsg(r.message);
      setSolved(r.solved);
    } catch (e: unknown) {
      setSubmitMsg(e instanceof Error ? e.message : String(e));
    }
  }

  if (error && !challenge) {
    return (
      <div className="card border-red-900 text-red-300">
        Could not load challenge: {error}
      </div>
    );
  }
  if (!challenge) return <p className="text-slate-500">Loading…</p>;

  return (
    <main className="space-y-8">
      {/* Header */}
      <header>
        <div className="flex items-start justify-between">
          <h1 className="text-3xl font-bold text-white">{challenge.title}</h1>
          <StatusPill solved={solved} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="badge">{challenge.category}</span>
          <span className="badge capitalize">{challenge.difficulty}</span>
          <span className="badge">{challenge.points} Points</span>
        </div>
        <p className="mt-4 max-w-2xl text-slate-400">{challenge.description}</p>
      </header>

      {/* Objective + learning objectives */}
      <section className="card">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-accent">
          Objective
        </h2>
        <p className="text-slate-300">
          ContentShield claims its proprietary model cannot be reproduced because the
          weights never leave the server. Prove that claim wrong: discover enough about
          the model through its public prediction interface to drive the target behavior.
        </p>
        {challenge.learning_objectives.length > 0 && (
          <ul className="mt-4 list-inside list-disc text-sm text-slate-400">
            {challenge.learning_objectives.map((o) => (
              <li key={o}>{o}</li>
            ))}
          </ul>
        )}
      </section>

      {/* Hints */}
      {challenge.hints.length > 0 && <Hints hints={challenge.hints} />}

      {/* API Console */}
      <section className="card">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-accent">
          Prediction API Console
        </h2>
        <label className="mb-1 block text-xs text-slate-500">Input text</label>
        <textarea
          className="input h-24 resize-y font-mono text-sm"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type text to classify…"
        />
        <div className="mt-3 flex items-center gap-3">
          <button className="btn" onClick={runPrediction} disabled={running}>
            {running ? "Running…" : "Run Prediction"}
          </button>
          <code className="text-xs text-slate-500">
            POST /api/challenges/{slug}/predict
          </code>
        </div>

        {history[0] && <PredictionResult item={history[0]} />}
      </section>

      {/* Request history */}
      {history.length > 1 && (
        <section className="card">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-accent">
            Request History
          </h2>
          <div className="space-y-2 text-sm">
            {history.slice(1).map((h, i) => (
              <div
                key={i}
                className="flex items-center justify-between gap-3 border-b border-edge pb-2 font-mono text-xs"
              >
                <span className="truncate text-slate-400">#{h.result.request_number} {h.input || "(empty)"}</span>
                <span className="shrink-0 text-slate-300">
                  {h.result.label} · {h.result.confidence.toFixed(3)}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Flag revealed banner */}
      {revealedFlag && (
        <section className="card border-green-800 bg-green-950/30">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wider text-green-400">
            Solve condition met
          </h2>
          <p className="text-sm text-slate-300">
            You drove the model to the target behavior. Here is your flag — submit it
            below to record the solve:
          </p>
          <code className="mt-2 block break-all rounded bg-ink p-2 font-mono text-green-300">
            {revealedFlag}
          </code>
        </section>
      )}

      {/* Flag submission */}
      <section className="card">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-accent">
          Flag Submission
        </h2>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            className="input font-mono"
            value={flag}
            onChange={(e) => setFlag(e.target.value)}
            placeholder="OWASP{…}"
          />
          <button className="btn shrink-0" onClick={doSubmit} disabled={!flag}>
            Submit Flag
          </button>
        </div>
        {submitMsg && (
          <p
            className={`mt-3 text-sm ${
              solved ? "text-green-400" : "text-slate-400"
            }`}
          >
            {submitMsg}
          </p>
        )}
      </section>
    </main>
  );
}

function StatusPill({ solved }: { solved: boolean }) {
  return (
    <span
      className={`badge ${
        solved ? "border-green-700 text-green-400" : "border-edge text-slate-400"
      }`}
    >
      Status: {solved ? "Solved" : "Not Solved"}
    </span>
  );
}

function PredictionResult({ item }: { item: HistoryItem }) {
  const { result } = item;
  const labels = Object.keys(result.probabilities);
  return (
    <div className="mt-4 rounded-lg border border-edge bg-ink p-4">
      <div className="flex items-center justify-between">
        <span className="font-semibold text-white">{result.label}</span>
        <span className="text-xs text-slate-500">request #{result.request_number}</span>
      </div>
      <div className="mt-1 text-sm text-slate-400">
        confidence: <span className="text-slate-200">{result.confidence.toFixed(3)}</span>
      </div>
      <div className="mt-3 space-y-2">
        {labels.map((l) => (
          <div key={l}>
            <div className="flex justify-between text-xs text-slate-400">
              <span>{l}</span>
              <span>{result.probabilities[l].toFixed(3)}</span>
            </div>
            <div className="mt-1 h-2 w-full rounded bg-edge">
              <div
                className="h-2 rounded bg-accent"
                style={{ width: `${Math.round(result.probabilities[l] * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
      {result.note && <p className="mt-3 text-xs text-slate-500">{result.note}</p>}
    </div>
  );
}

function Hints({ hints }: { hints: ChallengeDetail["hints"] }) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <section className="card">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-accent">
        Hints
      </h2>
      <div className="space-y-2">
        {hints.map((h) => (
          <div key={h.order} className="rounded-lg border border-edge">
            <button
              className="flex w-full items-center justify-between px-3 py-2 text-left text-sm"
              onClick={() => setOpen(open === h.order ? null : h.order)}
            >
              <span className="text-slate-300">
                Hint {h.order} {h.cost > 0 ? `— costs ${h.cost} pts` : "— free"}
              </span>
              <span className="text-slate-500">{open === h.order ? "−" : "+"}</span>
            </button>
            {open === h.order && (
              <p className="border-t border-edge px-3 py-2 text-sm text-slate-400">
                {h.text}
              </p>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
