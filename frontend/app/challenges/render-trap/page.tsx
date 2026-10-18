"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getChallenge,
  getPlayerId,
  renderTrapProof,
  renderTrapReset,
  renderTrapState,
  renderTrapSummarize,
  submitFlag,
  type ChallengeDetail,
  type RenderTrapState,
} from "@/lib/api";
import { Hints, StatusPill } from "@/components/challenge-ui";
import { RenderTrapPreview, type ProofEvent } from "@/components/render-trap-preview";

const SLUG = "render-trap";

export default function RenderTrapPage() {
  const [playerId, setPlayerId] = useState("local-player");
  const [challenge, setChallenge] = useState<ChallengeDetail | null>(null);
  const [state, setState] = useState<RenderTrapState | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [showRaw, setShowRaw] = useState(false);

  const [revealedFlag, setRevealedFlag] = useState<string | null>(null);
  const [flag, setFlag] = useState("");
  const [submitMsg, setSubmitMsg] = useState<string | null>(null);
  const [solved, setSolved] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);

  // Guards against a slow response overwriting a newer submit or a reset.
  const requestSeq = useRef(0);

  useEffect(() => {
    const pid = getPlayerId();
    setPlayerId(pid);
    Promise.all([getChallenge(SLUG, pid), renderTrapState(pid)])
      .then(([c, s]) => {
        setChallenge(c);
        setSolved(c.solved);
        setState(s);
        setNote(s.note);
      })
      .catch((e) => setError(e.message));
  }, []);

  async function summarize() {
    if (busy) return;
    const seq = ++requestSeq.current;
    setBusy(true);
    setFormError(null);
    setRevealedFlag(null);
    try {
      const s = await renderTrapSummarize(note, playerId);
      if (seq === requestSeq.current) setState(s);
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
      const s = await renderTrapReset(playerId);
      if (seq !== requestSeq.current) return;
      setState(s);
      setNote("");
      setFormError(null);
      setRevealedFlag(null);
      setShowRaw(false);
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : String(e));
    }
  }

  const onProof = useCallback(
    async (event: ProofEvent) => {
      try {
        const r = await renderTrapProof(event.generation, event.nonce, playerId);
        if (r.accepted && r.flag) {
          setRevealedFlag(r.flag);
          setFlag(r.flag);
          setState((cur) =>
            cur && cur.generation === r.state.generation ? r.state : cur
          );
        }
      } catch {
        /* a rejected or failed proof simply does nothing */
      }
    },
    [playerId]
  );

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

  const { ticket } = state;

  return (
    <main className="space-y-8">
      <header>
        <div className="flex items-start justify-between gap-4">
          <h1 className="text-3xl font-bold text-white">{challenge.title}</h1>
          <StatusPill solved={solved} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="badge border-accent/60 text-accent">OWASP LLM05:2025</span>
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
          Northstar Support&apos;s dashboard shows an AI-written summary of each customer
          ticket. Everything here is fictional and runs locally; the preview is sandboxed
          and cannot reach the platform, the network, or your data.
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
        {/* Ticket + note input */}
        <section className="card space-y-4">
          <div>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-accent">
              Ticket {ticket.id}
            </h2>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
              <dt className="text-slate-500">Customer</dt>
              <dd className="text-slate-200">{ticket.customer}</dd>
              <dt className="text-slate-500">Subject</dt>
              <dd className="text-slate-200">{ticket.subject}</dd>
              <dt className="text-slate-500">Priority</dt>
              <dd className="text-slate-200">{ticket.priority}</dd>
            </dl>
            <p className="mt-3 rounded-lg border border-edge bg-ink p-3 text-sm text-slate-400">
              {ticket.body}
            </p>
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              summarize();
            }}
          >
            <label htmlFor="rt-note" className="mb-1 block text-sm text-slate-300">
              Agent note for the summary
            </label>
            <textarea
              id="rt-note"
              className="input h-28 text-sm"
              value={note}
              maxLength={state.max_note_length}
              onChange={(e) => setNote(e.target.value)}
              aria-describedby="rt-note-help rt-note-error"
              placeholder="Add a note or request for the assistant…"
            />
            <div className="mt-1 flex justify-between text-xs text-slate-500">
              <span id="rt-note-help">Up to {state.max_note_length} characters.</span>
              <span>
                {note.length}/{state.max_note_length}
              </span>
            </div>
            <p id="rt-note-error" role="alert" className="mt-1 min-h-4 text-xs text-red-400">
              {formError}
            </p>
            <div className="mt-2 flex items-center gap-3">
              <button className="btn" type="submit" disabled={busy}>
                {busy ? "Generating…" : "Generate summary"}
              </button>
              <button type="button" className="text-xs text-slate-500 hover:text-accent" onClick={reset}>
                Reset environment
              </button>
            </div>
          </form>
        </section>

        {/* Output: raw text and sandboxed preview, kept clearly separate */}
        <div className="space-y-4">
          <section className="card">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
                Preview (sandboxed)
              </h2>
              <span className="text-xs text-slate-500">generation {state.generation}</span>
            </div>
            <RenderTrapPreview
              html={state.preview_html}
              generation={state.generation}
              onProof={onProof}
            />
          </section>

          <section className="card">
            <button
              className="flex w-full items-center justify-between text-left"
              onClick={() => setShowRaw((v) => !v)}
              aria-expanded={showRaw}
            >
              <span className="text-sm font-semibold uppercase tracking-wider text-accent">
                Raw assistant output
              </span>
              <span className="text-slate-500">{showRaw ? "−" : "+"}</span>
            </button>
            {showRaw && (
              <div className="mt-3">
                <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-edge bg-ink p-3 font-mono text-xs text-slate-300">
                  {state.raw_output ?? "No output yet."}
                </pre>
                <p className="mt-2 text-xs text-slate-500">
                  Diagnostics: the dashboard preview exposes a widget helper,{" "}
                  <code>rtPreview.confirm()</code>, to rich summaries.
                </p>
              </div>
            )}
          </section>
        </div>
      </div>

      {revealedFlag && (
        <section className="card border-green-800 bg-green-950/30">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wider text-green-400">
            Solve condition met
          </h2>
          <p className="text-sm text-slate-300">
            The preview executed generated markup and the backend verified the proof. Here
            is your flag — submit it below to record the solve:
          </p>
          <code className="mt-2 block break-all rounded bg-ink p-2 font-mono text-green-300">
            {revealedFlag}
          </code>
        </section>
      )}

      {state.challenge_solved && !revealedFlag && !solved && (
        <p className="text-sm text-slate-400">
          You already met the solve condition. Trigger the preview again to see your flag
          again.
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
