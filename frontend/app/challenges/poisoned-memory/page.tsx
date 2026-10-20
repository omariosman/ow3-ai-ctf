"use client";

import { useEffect, useRef, useState } from "react";
import {
  getChallenge,
  getPlayerId,
  submitFlag,
  poisonedMemoryAsk,
  poisonedMemoryEvidence,
  poisonedMemoryReset,
  poisonedMemoryState,
  poisonedMemoryInspect,
  type ChallengeDetail,
  type PoisonedMemoryState,
  type PoisonedMemoryRecordDetail,
} from "@/lib/api";
import { Hints, StatusPill } from "@/components/challenge-ui";

const SLUG = "poisoned-memory";

export default function PoisonedMemoryPage() {
  const [playerId, setPlayerId] = useState("local-player");
  const [challenge, setChallenge] = useState<ChallengeDetail | null>(null);
  const [state, setState] = useState<PoisonedMemoryState | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [record, setRecord] = useState<PoisonedMemoryRecordDetail | null>(null);

  const [marker, setMarker] = useState("");
  const [evidenceMsg, setEvidenceMsg] = useState<string | null>(null);
  const [revealedFlag, setRevealedFlag] = useState<string | null>(null);
  const [flag, setFlag] = useState("");
  const [submitMsg, setSubmitMsg] = useState<string | null>(null);
  const [solved, setSolved] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);

  // Guards against a slow response overwriting a newer action or a reset.
  const requestSeq = useRef(0);

  useEffect(() => {
    const pid = getPlayerId();
    setPlayerId(pid);
    Promise.all([getChallenge(SLUG, pid), poisonedMemoryState(pid)])
      .then(([c, s]) => {
        setChallenge(c);
        setSolved(c.solved);
        setState(s);
        setQuery(s.query);
      })
      .catch((e) => setError(e.message));
  }, []);

  const msg = (e: unknown) => (e instanceof Error ? e.message : String(e));

  async function ask() {
    if (busy) return;
    const seq = ++requestSeq.current;
    setBusy(true);
    setFormError(null);
    try {
      const s = await poisonedMemoryAsk(query, playerId);
      if (seq !== requestSeq.current) return;
      setState(s);
    } catch (e) {
      if (seq === requestSeq.current) setFormError(msg(e));
    } finally {
      if (seq === requestSeq.current) setBusy(false);
    }
  }

  async function inspect(recordId: string) {
    const seq = ++requestSeq.current;
    setFormError(null);
    try {
      const r = await poisonedMemoryInspect(recordId, playerId);
      if (seq !== requestSeq.current) return;
      setRecord(r.record);
      setState(r.state);
    } catch (e) {
      if (seq === requestSeq.current) setFormError(msg(e));
    }
  }

  async function reset() {
    const seq = ++requestSeq.current;
    setBusy(false);
    try {
      const s = await poisonedMemoryReset(playerId);
      if (seq !== requestSeq.current) return;
      setState(s);
      setQuery("");
      setRecord(null);
      setFormError(null);
      setEvidenceMsg(null);
      setRevealedFlag(null);
    } catch (e) {
      setFormError(msg(e));
    }
  }

  async function sendEvidence() {
    setEvidenceMsg(null);
    try {
      const r = await poisonedMemoryEvidence(marker, playerId);
      setState(r.state);
      if (r.flag) {
        setRevealedFlag(r.flag);
        setFlag(r.flag);
        setEvidenceMsg("Evidence verified by the server.");
      } else {
        setEvidenceMsg("Evidence not accepted. Ask the question, inspect the suspicious record and try again.");
      }
    } catch (e) {
      setEvidenceMsg(msg(e));
    }
  }

  async function doSubmit() {
    setSubmitMsg(null);
    try {
      const r = await submitFlag(SLUG, flag, playerId);
      setSubmitMsg(r.message);
      setSolved(r.solved);
    } catch (e) {
      setSubmitMsg(msg(e));
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
          <span className="badge border-accent/60 text-accent">OWASP LLM04:2025</span>
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
          You are auditing the Northstar Devices assistant, which answers from a small catalog
          of fictional support records. Objective: ask which replacement component is approved
          for the Northstar Mini, work out why the answer cannot be trusted, and submit the
          evidence from the tampered record. The data is the problem, not an instruction.
          Everything is fictional and runs locally with a deterministic simulator.
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
            <label htmlFor="pm-query" className="mb-1 block text-sm text-slate-300">
              Ask the Northstar Devices assistant
            </label>
            <textarea
              id="pm-query"
              className="input h-20 text-sm"
              value={query}
              maxLength={state.max_query_length}
              onChange={(e) => setQuery(e.target.value)}
              aria-describedby="pm-query-error"
              placeholder="e.g. Which replacement component is approved for the Northstar Mini?"
            />
            <p id="pm-query-error" role="alert" className="mt-1 min-h-4 text-xs text-red-400">
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
            Retrieved records
          </h2>
          {state.retrieved.length === 0 ? (
            <p className="text-sm text-slate-500">No records retrieved for this turn.</p>
          ) : (
            <ul className="space-y-2">
              {state.retrieved.map((r) => (
                <li key={r.record_id} className="rounded-lg border border-edge px-3 py-2 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-slate-300">
                      #{r.rank} {r.source}
                    </span>
                    <span className="badge">{r.trust}</span>
                  </div>
                  <p className="mt-1 font-mono text-xs text-slate-500">
                    {r.record_id} · relevance {r.relevance} · score {r.score}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="card">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-accent">
          Record inspector
        </h2>
        <div className="flex flex-wrap gap-2">
          {state.records.map((r) => (
            <button
              key={r.record_id}
              className="badge hover:border-accent"
              onClick={() => inspect(r.record_id)}
            >
              {r.source} ({r.trust})
            </button>
          ))}
        </div>
        {record && (
          <div className="mt-4 space-y-2 rounded-lg border border-edge bg-ink p-3 text-sm">
            <p className="font-mono text-xs text-slate-500">{record.record_id}</p>
            <p className="text-slate-300">
              {record.source} · trust: {record.trust}
            </p>
            <p className="text-xs text-slate-400">Integrity: {record.integrity}</p>
            <pre className="whitespace-pre-wrap break-words font-mono text-xs text-slate-300">
              {record.content}
            </pre>
            {record.note && <p className="font-mono text-xs text-amber-300">{record.note}</p>}
          </div>
        )}
      </section>

      <section className="card">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-accent">
          Evidence
        </h2>
        <p className="mb-3 text-sm text-slate-400">
          Enter the marker found in the tampered record. The server checks the poisoned answer and
          that you inspected the record; the marker alone is not the flag.
        </p>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            className="input font-mono"
            aria-label="Evidence"
            value={marker}
            maxLength={100}
            onChange={(e) => setMarker(e.target.value)}
            placeholder="Marker"
          />
          <button className="btn shrink-0" onClick={sendEvidence} disabled={!marker.trim()}>
            Submit Evidence
          </button>
        </div>
        {evidenceMsg && <p className="mt-3 text-sm text-slate-400">{evidenceMsg}</p>}
      </section>

      {revealedFlag && (
        <section className="card border-green-800 bg-green-950/30">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wider text-green-400">
            Solve condition met
          </h2>
          <p className="text-sm text-slate-300">
            The server verified your evidence. Here is your flag — submit it below to record the
            solve:
          </p>
          <code className="mt-2 block break-all rounded bg-ink p-2 font-mono text-green-300">
            {revealedFlag}
          </code>
        </section>
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
