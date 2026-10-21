"use client";

import { useEffect, useState } from "react";
import {
  getChallenge,
  getPlayerId,
  submitFlag,
  tenantZeroOpen,
  tenantZeroPolicy,
  tenantZeroReset,
  tenantZeroSearch,
  tenantZeroState,
  tenantZeroSummary,
  tenantZeroVerify,
  type ChallengeDetail,
  type TenantZeroPolicy,
  type TenantZeroSearchResult,
  type TenantZeroState,
} from "@/lib/api";
import { Hints, StatusPill } from "@/components/challenge-ui";

const SLUG = "tenant-zero";

const POLICY_FIELDS: { key: keyof TenantZeroPolicy; label: string }[] = [
  { key: "enforce_ownership", label: "Enforce conversation ownership" },
  { key: "scope_search_to_tenant", label: "Scope search to the caller's tenant" },
  { key: "redact_sensitive_fields", label: "Redact sensitive fields" },
  { key: "enforcement_enabled", label: "Enforcement enabled (master switch)" },
];

export default function TenantZeroPage() {
  const [playerId, setPlayerId] = useState("local-player");
  const [challenge, setChallenge] = useState<ChallengeDetail | null>(null);
  const [state, setState] = useState<TenantZeroState | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [convId, setConvId] = useState("conv-1001");
  const [query, setQuery] = useState("");
  const [shown, setShown] = useState<{ title: string; body: string } | null>(null);
  const [results, setResults] = useState<TenantZeroSearchResult[] | null>(null);
  const [draft, setDraft] = useState<TenantZeroPolicy | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const [revealedFlag, setRevealedFlag] = useState<string | null>(null);
  const [flag, setFlag] = useState("");
  const [submitMsg, setSubmitMsg] = useState<string | null>(null);
  const [solved, setSolved] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);

  useEffect(() => {
    const pid = getPlayerId();
    setPlayerId(pid);
    Promise.all([getChallenge(SLUG, pid), tenantZeroState(pid)])
      .then(([c, s]) => {
        setChallenge(c);
        setSolved(c.solved);
        setState(s);
        setDraft(s.policy);
      })
      .catch((e) => setError(e.message));
  }, []);

  const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));

  async function view(kind: "open" | "summary") {
    setMsg(null);
    setResults(null);
    try {
      const r = await (kind === "open" ? tenantZeroOpen : tenantZeroSummary)(convId, playerId);
      setState(r.state);
      setShown(
        r.allowed
          ? { title: `${kind === "open" ? "Conversation" : "Summary"} ${convId}`, body: JSON.stringify(r.conversation, null, 2) }
          : null
      );
      setMsg(r.allowed ? "ok" : r.message);
    } catch (e) {
      setMsg(errText(e));
    }
  }

  async function doSearch() {
    setMsg(null);
    setShown(null);
    try {
      const r = await tenantZeroSearch(query, playerId);
      setState(r.state);
      setResults(r.results);
    } catch (e) {
      setMsg(errText(e));
    }
  }

  async function applyPolicy() {
    if (!draft) return;
    setMsg(null);
    try {
      setState(await tenantZeroPolicy(draft, playerId));
      setMsg("Policy applied. Run the verification to test it.");
    } catch (e) {
      setMsg(errText(e));
    }
  }

  async function verify() {
    setMsg(null);
    try {
      const r = await tenantZeroVerify(playerId);
      setState(r.state);
      if (r.flag) {
        setRevealedFlag(r.flag);
        setFlag(r.flag);
      } else {
        setMsg(
          r.state.leak_demonstrated
            ? "Verification did not pass. Review the failed checks."
            : "Reproduce the leak against the vulnerable service first."
        );
      }
    } catch (e) {
      setMsg(errText(e));
    }
  }

  async function reset() {
    try {
      const s = await tenantZeroReset(playerId);
      setState(s);
      setDraft(s.policy);
      setShown(null);
      setResults(null);
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

  return (
    <main className="space-y-8">
      <header>
        <div className="flex items-start justify-between gap-4">
          <h1 className="text-3xl font-bold text-white">{challenge.title}</h1>
          <StatusPill solved={solved} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="badge border-accent/60 text-accent">OWASP LLM02:2025</span>
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
          You are {state.tenant_name}. Stage 1: look for conversations you should not be able to
          reach. Stage 2: set an access policy that closes the leak. Stage 3: verify that other
          tenants are blocked and your own history still works. All data is fictional and the
          server decides who you are.
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

      <section className="card">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-accent">
          Service status
        </h2>
        <p className="text-sm text-slate-300">
          Your conversations:{" "}
          {state.own_conversations.map((c) => `${c.conv_id} (${c.subject})`).join(", ")}
        </p>
        <p className="mt-1 text-xs text-slate-500">
          Mode: {state.policy.enforcement_enabled ? "controls enforced" : "no controls enforced (vulnerable)"} ·
          Leak reproduced: {state.leak_demonstrated ? "yes" : "not yet"} · Hardening verified:{" "}
          {state.hardening_verified ? "yes" : "no"}
        </p>
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        <section className="card space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
            Conversation viewer
          </h2>
          <label className="block text-sm text-slate-300">
            Conversation id
            <input
              className="input mt-1 font-mono"
              value={convId}
              maxLength={9}
              onChange={(e) => setConvId(e.target.value)}
              placeholder="conv-1001"
            />
          </label>
          <div className="flex gap-3">
            <button className="btn" onClick={() => view("open")}>
              Open
            </button>
            <button className="btn-ghost text-sm" onClick={() => view("summary")}>
              Summarize
            </button>
          </div>
          <label className="block text-sm text-slate-300">
            Similar past cases
            <input
              className="input mt-1"
              value={query}
              maxLength={state.max_query_length}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. password"
            />
          </label>
          <div className="flex items-center gap-3">
            <button className="btn-ghost text-sm" onClick={doSearch} disabled={!query.trim()}>
              Search
            </button>
            <button className="text-xs text-slate-500 hover:text-accent" onClick={reset}>
              Reset environment
            </button>
          </div>
          {msg && (
            <p role="status" className="text-sm text-slate-300">
              {msg}
            </p>
          )}
        </section>

        <section className="card">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-accent">
            Result
          </h2>
          {shown && (
            <div>
              <p className="mb-1 text-xs text-slate-500">{shown.title}</p>
              <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-edge bg-ink p-3 font-mono text-xs text-slate-300">
                {shown.body}
              </pre>
            </div>
          )}
          {results && (
            <ul className="space-y-2 text-sm">
              {results.length === 0 && <li className="text-slate-500">No results.</li>}
              {results.map((r) => (
                <li key={r.conv_id} className="rounded-lg border border-edge px-3 py-2">
                  <span className="font-mono text-slate-300">{r.conv_id}</span>{" "}
                  <span className="badge">{r.tenant_name}</span>
                  <p className="mt-1 text-slate-400">{r.subject}: {r.snippet}</p>
                </li>
              ))}
            </ul>
          )}
          {!shown && !results && (
            <p className="text-sm text-slate-500">Open a conversation or run a search.</p>
          )}
        </section>
      </div>

      <section className="card space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
          Access policy editor
        </h2>
        {POLICY_FIELDS.map((f) => (
          <label key={f.key} className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={draft[f.key]}
              onChange={(e) => setDraft({ ...draft, [f.key]: e.target.checked })}
            />
            {f.label}
          </label>
        ))}
        <button className="btn" onClick={applyPolicy}>
          Apply policy
        </button>
      </section>

      <section className="card">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-accent">
          Verification panel
        </h2>
        <p className="mb-3 text-sm text-slate-400">
          Tests cross-tenant and legitimate requests against your applied policy. Requires that
          you reproduced the leak first.
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
            The server verified your policy. Here is your flag — submit it below to record the
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
