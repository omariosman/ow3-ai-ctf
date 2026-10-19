"use client";

import { useEffect, useRef, useState } from "react";
import {
  contextHijackAsk,
  contextHijackReset,
  contextHijackState,
  getChallenge,
  getPlayerId,
  submitFlag,
  type ChallengeDetail,
  type ContextHijackState,
} from "@/lib/api";
import { Hints, StatusPill } from "@/components/challenge-ui";

const SLUG = "context-hijack";

function TrustBadge({ trusted }: { trusted: boolean }) {
  return trusted ? (
    <span className="badge border-green-700 text-green-400">Official / trusted</span>
  ) : (
    <span className="badge border-red-800 text-red-400">External / untrusted</span>
  );
}

export default function ContextHijackPage() {
  const [playerId, setPlayerId] = useState("local-player");
  const [challenge, setChallenge] = useState<ChallengeDetail | null>(null);
  const [state, setState] = useState<ContextHijackState | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [openDoc, setOpenDoc] = useState<string | null>(null);

  const [revealedFlag, setRevealedFlag] = useState<string | null>(null);
  const [flag, setFlag] = useState("");
  const [submitMsg, setSubmitMsg] = useState<string | null>(null);
  const [solved, setSolved] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);

  // Guards against a slow response overwriting a newer ask or a reset.
  const requestSeq = useRef(0);

  useEffect(() => {
    const pid = getPlayerId();
    setPlayerId(pid);
    Promise.all([getChallenge(SLUG, pid), contextHijackState(pid)])
      .then(([c, s]) => {
        setChallenge(c);
        setSolved(c.solved);
        setState(s);
        setQuery(s.query);
      })
      .catch((e) => setError(e.message));
  }, []);

  async function ask() {
    if (busy) return;
    const seq = ++requestSeq.current;
    setBusy(true);
    setFormError(null);
    setRevealedFlag(null);
    try {
      const r = await contextHijackAsk(query, playerId);
      if (seq !== requestSeq.current) return;
      setState(r.state);
      if (r.flag) {
        setRevealedFlag(r.flag);
        setFlag(r.flag);
      }
    } catch (e: unknown) {
      if (seq === requestSeq.current)
        setFormError(e instanceof Error ? e.message : String(e));
    } finally {
      if (seq === requestSeq.current) setBusy(false);
    }
  }

  async function reset() {
    const seq = ++requestSeq.current;
    setBusy(false);
    try {
      const s = await contextHijackReset(playerId);
      if (seq !== requestSeq.current) return;
      setState(s);
      setQuery("");
      setFormError(null);
      setRevealedFlag(null);
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : String(e));
    }
  }

  async function doSubmit() {
    setSubmitMsg(null);
    try {
      const r = await submitFlag(SLUG, flag, playerId);
      setSubmitMsg(r.message);
      setSolved(r.solved);
    } catch (e: unknown) {
      setSubmitMsg(e instanceof Error ? e.message : String(e));
    }
  }

  if (error && !challenge) {
    return (
      <div className="card border-red-900 text-red-300">Could not load challenge: {error}</div>
    );
  }
  if (!challenge || !state) return <p className="text-slate-500">Loading…</p>;

  return (
    <main className="space-y-8">
      <header>
        <div className="flex items-start justify-between gap-4">
          <h1 className="text-3xl font-bold text-white">{challenge.title}</h1>
          <StatusPill solved={solved} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="badge border-accent/60 text-accent">OWASP LLM01:2025</span>
          <span className="badge">{challenge.category}</span>
          <span className="badge capitalize">{challenge.difficulty}</span>
          <span className="badge">{challenge.points} Points</span>
        </div>
        <p className="mt-4 max-w-2xl text-slate-400">{challenge.description}</p>
      </header>

      <section className="card">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-accent">
          Scenario
        </h2>
        <p className="text-slate-300">
          You are auditing HelpDesk Atlas, a fictional support assistant that answers from a
          small knowledge base. Objective: ask an ordinary support question and work out why
          the answer does not match the official policy. Everything is fictional and runs
          locally with a deterministic simulator.
        </p>
        {challenge.learning_objectives.length > 0 && (
          <ul className="mt-4 list-inside list-disc text-sm text-slate-400">
            {challenge.learning_objectives.map((o) => (
              <li key={o}>{o}</li>
            ))}
          </ul>
        )}
      </section>

      {challenge.hints.length > 0 && <Hints hints={challenge.hints} />}

      <div className="grid gap-4 md:grid-cols-2">
        <section className="card space-y-4">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              ask();
            }}
          >
            <label htmlFor="ch-query" className="mb-1 block text-sm text-slate-300">
              Ask HelpDesk Atlas
            </label>
            <textarea
              id="ch-query"
              className="input h-24 text-sm"
              value={query}
              maxLength={state.max_query_length}
              onChange={(e) => setQuery(e.target.value)}
              aria-describedby="ch-query-error"
              placeholder="e.g. What is the return policy for an unopened item?"
            />
            <div className="mt-1 text-right text-xs text-slate-500">
              {query.length}/{state.max_query_length}
            </div>
            <p id="ch-query-error" role="alert" className="mt-1 min-h-4 text-xs text-red-400">
              {formError}
            </p>
            <div className="mt-2 flex items-center gap-3">
              <button className="btn" type="submit" disabled={busy || !query.trim()}>
                {busy ? "Asking…" : "Ask"}
              </button>
              <button
                type="button"
                className="text-xs text-slate-500 hover:text-accent"
                onClick={reset}
              >
                Reset environment
              </button>
            </div>
          </form>

          <div>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-accent">
              Assistant response
            </h2>
            <p className="whitespace-pre-wrap break-words rounded-lg border border-edge bg-ink p-3 text-sm text-slate-200">
              {state.response ?? "No question asked yet."}
            </p>
          </div>
        </section>

        <section className="card">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-accent">
            Retrieved sources
          </h2>
          {state.sources.length === 0 ? (
            <p className="text-sm text-slate-500">No sources retrieved for this turn.</p>
          ) : (
            <ul className="space-y-2">
              {state.sources.map((s) => (
                <li
                  key={s.doc_id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-edge px-3 py-2"
                >
                  <code className="text-sm text-slate-300">{s.doc_id}</code>
                  <TrustBadge trusted={s.trusted} />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="card">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-accent">
          Knowledge base
        </h2>
        <div className="space-y-2">
          {state.documents.map((d) => (
            <div key={d.doc_id} className="rounded-lg border border-edge">
              <button
                className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm"
                onClick={() => setOpenDoc(openDoc === d.doc_id ? null : d.doc_id)}
                aria-expanded={openDoc === d.doc_id}
              >
                <span className="flex flex-wrap items-center gap-2">
                  <code className="text-slate-300">{d.doc_id}</code>
                  <TrustBadge trusted={d.trusted} />
                </span>
                <span className="text-slate-500">{openDoc === d.doc_id ? "−" : "+"}</span>
              </button>
              {openDoc === d.doc_id && (
                <div className="border-t border-edge px-3 py-2">
                  <p className="mb-2 text-xs text-slate-500">Source: {d.source}</p>
                  <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words font-mono text-xs text-slate-300">
                    {d.content}
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {revealedFlag && (
        <section className="card border-green-800 bg-green-950/30">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wider text-green-400">
            Solve condition met
          </h2>
          <p className="text-sm text-slate-300">
            The server verified that a retrieved external document steered the answer. Here is
            your flag — submit it below to record the solve:
          </p>
          <code className="mt-2 block break-all rounded bg-ink p-2 font-mono text-green-300">
            {revealedFlag}
          </code>
        </section>
      )}

      {state.challenge_solved && !revealedFlag && !solved && (
        <p className="text-sm text-slate-400">
          You already met the solve condition. Ask the question again to see your flag again.
        </p>
      )}

      <section className="card">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-accent">
          Flag Submission
        </h2>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            className="input font-mono"
            aria-label="Flag"
            value={flag}
            onChange={(e) => setFlag(e.target.value)}
            placeholder="OWASP{…}"
          />
          <button className="btn shrink-0" onClick={doSubmit} disabled={!flag}>
            Submit Flag
          </button>
        </div>
        {submitMsg && (
          <p className={`mt-3 text-sm ${solved ? "text-green-400" : "text-slate-400"}`}>
            {submitMsg}
          </p>
        )}
      </section>

      {state.analysis && (
        <section className="card">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
              What happened?
            </h2>
            <button className="btn-ghost text-sm" onClick={() => setShowAnalysis((v) => !v)}>
              {showAnalysis ? "Hide" : "View"} Security Analysis
            </button>
          </div>
          <ul className="mt-3 space-y-1 text-sm text-slate-300">
            {state.analysis.what_happened.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          {showAnalysis && (
            <div className="mt-4 space-y-3 rounded-lg border border-edge bg-ink p-4 font-mono text-xs">
              <p>
                <span className="text-slate-500">OWASP:</span> {state.analysis.owasp}
              </p>
              <p>
                <span className="text-slate-500">Root cause:</span> {state.analysis.root_cause}
              </p>
              <div>
                <p className="text-red-400">Broken</p>
                <pre className="whitespace-pre-wrap text-slate-300">{state.analysis.broken}</pre>
              </div>
              <div>
                <p className="text-green-400">Secure</p>
                <pre className="whitespace-pre-wrap text-slate-300">{state.analysis.secure}</pre>
              </div>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
