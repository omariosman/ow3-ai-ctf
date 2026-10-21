"use client";

import { useEffect, useState } from "react";
import {
  getChallenge,
  getPlayerId,
  submitFlag,
  tokenStormPolicy,
  tokenStormRequest,
  tokenStormReset,
  tokenStormState,
  tokenStormVerify,
  type ChallengeDetail,
  type TokenStormPolicy,
  type TokenStormState,
} from "@/lib/api";
import { Hints, StatusPill } from "@/components/challenge-ui";

const SLUG = "token-storm";

const PRESETS = [
  { label: "normal", input: 200, output: 100 },
  { label: "large-input", input: 6000, output: 100 },
  { label: "large-output", input: 200, output: 3000 },
];

const POLICY_FIELDS: { key: keyof Omit<TokenStormPolicy, "enforcement_enabled">; label: string; max: number }[] = [
  { key: "max_input_tokens", label: "Max input tokens", max: 100000 },
  { key: "max_output_tokens", label: "Max output tokens", max: 100000 },
  { key: "max_requests", label: "Request quota", max: 1000 },
  { key: "max_total_cost", label: "Budget ceiling (units)", max: 100 },
];

export default function TokenStormPage() {
  const [playerId, setPlayerId] = useState("local-player");
  const [challenge, setChallenge] = useState<ChallengeDetail | null>(null);
  const [state, setState] = useState<TokenStormState | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [input, setInput] = useState("200");
  const [output, setOutput] = useState("100");
  const [draft, setDraft] = useState<TokenStormPolicy | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const [revealedFlag, setRevealedFlag] = useState<string | null>(null);
  const [flag, setFlag] = useState("");
  const [submitMsg, setSubmitMsg] = useState<string | null>(null);
  const [solved, setSolved] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);

  useEffect(() => {
    const pid = getPlayerId();
    setPlayerId(pid);
    Promise.all([getChallenge(SLUG, pid), tokenStormState(pid)])
      .then(([c, s]) => {
        setChallenge(c);
        setSolved(c.solved);
        setState(s);
        setDraft(s.policy);
      })
      .catch((e) => setError(e.message));
  }, []);

  const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));

  async function send() {
    setMsg(null);
    try {
      const r = await tokenStormRequest(Number(input), Number(output), playerId);
      setState(r.state);
      setMsg(r.result.message);
    } catch (e) {
      setMsg(errText(e));
    }
  }

  async function applyPolicy() {
    if (!draft) return;
    setMsg(null);
    try {
      const s = await tokenStormPolicy(draft, playerId);
      setState(s);
      setMsg("Policy applied. Run the verification to test it.");
    } catch (e) {
      setMsg(errText(e));
    }
  }

  async function verify() {
    setMsg(null);
    try {
      const r = await tokenStormVerify(playerId);
      setState(r.state);
      if (r.flag) {
        setRevealedFlag(r.flag);
        setFlag(r.flag);
      } else {
        setMsg(
          r.state.abuse_demonstrated
            ? "Verification did not pass. Review the failed checks."
            : "Reproduce the abuse against the vulnerable gateway first."
        );
      }
    } catch (e) {
      setMsg(errText(e));
    }
  }

  async function reset() {
    try {
      const s = await tokenStormReset(playerId);
      setState(s);
      setDraft(s.policy);
      setRevealedFlag(null);
      setMsg(null);
    } catch (e) {
      setMsg(errText(e));
    }
  }

  async function doSubmit() {
    setSubmitMsg(null);
    try {
      const r = await submitFlag(SLUG, flag, playerId);
      setSubmitMsg(r.message);
      setSolved(r.solved);
    } catch (e) {
      setSubmitMsg(errText(e));
    }
  }

  if (error && !challenge) {
    return (
      <div className="card border-red-900 text-red-300">Could not load challenge: {error}</div>
    );
  }
  if (!challenge || !state || !draft) return <p className="text-slate-500">Loading…</p>;

  const pct = Math.round((state.remaining_budget / state.initial_budget) * 100);

  return (
    <main className="space-y-8">
      <header>
        <div className="flex items-start justify-between gap-4">
          <h1 className="text-3xl font-bold text-white">{challenge.title}</h1>
          <StatusPill solved={solved} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="badge border-accent/60 text-accent">OWASP LLM10:2025</span>
          <span className="badge">{challenge.category}</span>
          <span className="badge capitalize">{challenge.difficulty}</span>
          <span className="badge">{challenge.points} Points</span>
        </div>
        <p className="mt-4 max-w-2xl text-slate-400">{challenge.description}</p>
      </header>

      <section className="card">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-accent">
          Mission brief
        </h2>
        <p className="text-slate-300">
          Stage 1: reproduce the budget drain with the request builder. Stage 2: set a policy that
          blocks abuse. Stage 3: verify that abuse is blocked and a normal request still works.
          All token counts and costs are simulated; nothing real is called.
        </p>
        <p className="mt-2 font-mono text-xs text-slate-400">{state.cost_formula}</p>
        {challenge.learning_objectives.length > 0 && (
          <ul className="mt-4 list-inside list-disc text-sm text-slate-400">
            {challenge.learning_objectives.map((o) => (
              <li key={o}>{o}</li>
            ))}
          </ul>
        )}
      </section>

      {challenge.hints.length > 0 && <Hints hints={challenge.hints} />}

      <section className="card">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-accent">
          Gateway status
        </h2>
        <p className="text-sm text-slate-300">
          Budget: {state.remaining_budget} / {state.initial_budget} units ({pct}%) · Accepted
          requests: {state.request_count} · Mode:{" "}
          {state.policy.enforcement_enabled ? "limits enforced" : "no limits enforced (vulnerable)"}
        </p>
        <div
          className="mt-2 h-2 w-full rounded bg-ink"
          role="progressbar"
          aria-label="Remaining simulated budget"
          aria-valuenow={state.remaining_budget}
          aria-valuemin={0}
          aria-valuemax={state.initial_budget}
        >
          <div className="h-2 rounded bg-accent" style={{ width: `${pct}%` }} />
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Abuse reproduced: {state.abuse_demonstrated ? "yes" : "not yet"} · Hardening verified:{" "}
          {state.hardening_verified ? "yes" : "no"}
        </p>
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        <section className="card space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
            Request builder
          </h2>
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((p) => (
              <button
                key={p.label}
                className="badge hover:border-accent"
                onClick={() => {
                  setInput(String(p.input));
                  setOutput(String(p.output));
                }}
              >
                {p.label}
              </button>
            ))}
          </div>
          <label className="block text-sm text-slate-300">
            Input tokens (simulated)
            <input
              className="input mt-1 font-mono"
              type="number"
              min={0}
              max={100000}
              step={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
          </label>
          <label className="block text-sm text-slate-300">
            Requested output tokens (simulated)
            <input
              className="input mt-1 font-mono"
              type="number"
              min={0}
              max={100000}
              step={1}
              value={output}
              onChange={(e) => setOutput(e.target.value)}
            />
          </label>
          <div className="flex items-center gap-3">
            <button className="btn" onClick={send}>
              Send request
            </button>
            <button
              className="text-xs text-slate-500 hover:text-accent"
              onClick={reset}
            >
              Reset environment
            </button>
          </div>
          {msg && (
            <p role="status" className="text-sm text-slate-300">
              {msg}
            </p>
          )}
        </section>

        <section className="card space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
            Policy editor
          </h2>
          {POLICY_FIELDS.map((f) => (
            <label key={f.key} className="block text-sm text-slate-300">
              {f.label} (1–{f.max})
              <input
                className="input mt-1 font-mono"
                type="number"
                min={1}
                max={f.max}
                step={1}
                value={draft[f.key]}
                onChange={(e) => setDraft({ ...draft, [f.key]: Number(e.target.value) })}
              />
            </label>
          ))}
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={draft.enforcement_enabled}
              onChange={(e) => setDraft({ ...draft, enforcement_enabled: e.target.checked })}
            />
            Enforcement enabled
          </label>
          <button className="btn" onClick={applyPolicy}>
            Apply policy
          </button>
        </section>
      </div>

      <section className="card">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-accent">
          Request history
        </h2>
        {state.history.length === 0 ? (
          <p className="text-sm text-slate-500">No requests yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="text-slate-500">
                <tr>
                  <th className="pr-3">Outcome</th>
                  <th className="pr-3">Input</th>
                  <th className="pr-3">Output</th>
                  <th className="pr-3">Cost</th>
                  <th className="pr-3">Charged</th>
                  <th className="pr-3">Remaining</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {state.history.map((h, i) => (
                  <tr key={i}>
                    <td className="pr-3">{h.accepted ? "Accepted" : "Rejected"}</td>
                    <td className="pr-3">{h.input_tokens}</td>
                    <td className="pr-3">{h.output_tokens}</td>
                    <td className="pr-3">{h.cost}</td>
                    <td className="pr-3">{h.charged}</td>
                    <td className="pr-3">{h.remaining_budget}</td>
                    <td>{h.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-accent">
          Verification panel
        </h2>
        <p className="mb-3 text-sm text-slate-400">
          Runs abusive and normal requests against your applied policy on a separate simulated
          ledger. Requires that you reproduced the abuse first.
        </p>
        <button className="btn" onClick={verify}>
          Verify hardening
        </button>
        {state.checks.length > 0 && (
          <ul className="mt-3 space-y-1 text-sm">
            {state.checks.map((c) => (
              <li key={c.name} className={c.passed ? "text-green-400" : "text-red-400"}>
                {c.passed ? "PASS" : "FAIL"} — {c.name}{" "}
                <span className="text-slate-500">({c.message})</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {revealedFlag && (
        <section className="card border-green-800 bg-green-950/30">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wider text-green-400">
            Solve condition met
          </h2>
          <p className="text-sm text-slate-300">
            The server verified your hardened gateway. Here is your flag — submit it below to
            record the solve:
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
