"use client";

import { useEffect, useState } from "react";
import {
  getChallenge,
  getPlayerId,
  modelCrateAction,
  modelCrateReset,
  modelCrateState,
  submitFlag,
  type ChallengeDetail,
  type ModelCrateAction,
  type ModelCrateState,
} from "@/lib/api";
import { Hints, StatusPill } from "@/components/challenge-ui";

const SLUG = "model-crate";
const STEPS = ["UNVERIFIED", "INSPECTED", "MISMATCH_CONFIRMED", "QUARANTINED"] as const;

function Hash({ value, tone }: { value: string; tone?: "ok" | "bad" }) {
  const color = tone === "ok" ? "text-green-300" : tone === "bad" ? "text-red-300" : "text-slate-300";
  return <code className={`break-all font-mono text-xs ${color}`}>{value || "(none)"}</code>;
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <>
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-slate-200">{children}</dd>
    </>
  );
}

export default function ModelCratePage() {
  const [playerId, setPlayerId] = useState("local-player");
  const [challenge, setChallenge] = useState<ChallengeDetail | null>(null);
  const [state, setState] = useState<ModelCrateState | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [revealedFlag, setRevealedFlag] = useState<string | null>(null);
  const [flag, setFlag] = useState("");
  const [submitMsg, setSubmitMsg] = useState<string | null>(null);
  const [solved, setSolved] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);

  useEffect(() => {
    const pid = getPlayerId();
    setPlayerId(pid);
    Promise.all([getChallenge(SLUG, pid), modelCrateState(pid)])
      .then(([c, s]) => {
        setChallenge(c);
        setSolved(c.solved);
        setState(s);
      })
      .catch((e) => setError(e.message));
  }, []);

  async function run(action: ModelCrateAction) {
    if (busy) return;
    setBusy(true);
    setActionError(null);
    try {
      const r = await modelCrateAction(action, playerId);
      setState(r.state);
      setMessage(r.message);
      if (r.flag) {
        setRevealedFlag(r.flag);
        setFlag(r.flag);
      }
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : String(e));
      // The server may have recorded an event (e.g. a blocked load); refresh.
      modelCrateState(playerId).then(setState).catch(() => {});
    } finally {
      setBusy(false);
    }
  }

  async function reset() {
    setBusy(true);
    try {
      setState(await modelCrateReset(playerId));
      setMessage(null);
      setActionError(null);
      setRevealedFlag(null);
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
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

  const { inventory, trusted_release: tr, package_manifest: pm, artifact, comparison } = state;
  const stepIndex = STEPS.indexOf(state.status);
  const quarantined = state.status === "QUARANTINED";
  const inspected = state.status !== "UNVERIFIED";
  const failed = state.status === "MISMATCH_CONFIRMED" || quarantined;

  return (
    <main className="space-y-8">
      <header>
        <div className="flex items-start justify-between gap-4">
          <h1 className="text-3xl font-bold text-white">{challenge.title}</h1>
          <StatusPill solved={solved} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="badge border-accent/60 text-accent">OWASP LLM03:2025</span>
          <span className="badge">{challenge.category}</span>
          <span className="badge capitalize">{challenge.difficulty}</span>
          <span className="badge">{challenge.points} Points</span>
        </div>
        <p className="mt-4 max-w-2xl text-slate-400">{challenge.description}</p>
      </header>

      <section className="card">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-accent">
          Incident
        </h2>
        <p className="text-slate-300">{state.incident}</p>
        <p className="mt-2 text-xs text-slate-500">
          Local simulation: the artifact is an inert text fixture. It is hashed, never loaded or
          executed, and the provenance check is simulated (no real cryptography).
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

      <ol className="flex flex-wrap gap-2 text-xs" aria-label="Verification state">
        {STEPS.map((s, i) => (
          <li
            key={s}
            aria-current={i === stepIndex ? "step" : undefined}
            className={`badge ${
              i === stepIndex
                ? s === "QUARANTINED"
                  ? "border-green-700 text-green-400"
                  : "border-accent/60 text-accent"
                : i < stepIndex
                  ? "text-slate-300"
                  : "text-slate-600"
            }`}
          >
            {s}
          </li>
        ))}
      </ol>

      <div className="grid gap-4 md:grid-cols-2">
        <section className="card space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
            Release inventory
          </h2>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
            <Row label="Component">{inventory.component}</Row>
            <Row label="Version">{inventory.version}</Row>
            <Row label="Artifact">{inventory.artifact_id}</Row>
            <Row label="Publisher">{inventory.publisher}</Row>
            <Row label="Status">
              <span className="badge">{inventory.status}</span>
            </Row>
          </dl>
          <h3 className="pt-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Bundled manifest (shipped inside the package, untrusted)
          </h3>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
            <Row label="Claimed digest">
              <Hash value={pm.claimed_sha256} />
            </Row>
            <Row label="Signer">{pm.attestation.signer}</Row>
            <Row label="Source">{pm.attestation.source_repository}</Row>
            <Row label="Signed digest">
              <Hash value={pm.attestation.signed_sha256} />
            </Row>
            <Row label="Build">{pm.attestation.build_id}</Row>
          </dl>
        </section>

        <section className="card space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
            Trusted release record
          </h2>
          <p className="text-xs text-slate-500">
            Authored by release engineering, independent of the artifact you received.
          </p>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
            <Row label="Version">{tr.version}</Row>
            <Row label="Expected SHA-256">
              <Hash value={tr.expected_sha256} tone="ok" />
            </Row>
            <Row label="Source">{tr.source_repository}</Row>
            <Row label="Approved signers">{tr.approved_signers.join(", ")}</Row>
            <Row label="Signature">{tr.signature_required ? "required" : "optional"}</Row>
            <Row label="Approved by">
              {tr.approver} · {tr.approved_on}
            </Row>
          </dl>
        </section>
      </div>

      <section className="card space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
          Artifact inspection
        </h2>
        {!artifact ? (
          <p className="text-sm text-slate-500">
            Not inspected yet. Inspecting hashes the received bytes on the server.
          </p>
        ) : (
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
            <Row label="Artifact">
              {artifact.artifact_id} ({artifact.size_bytes} bytes)
            </Row>
            <Row label="Claimed version">{artifact.claimed_version}</Row>
            <Row label="Actual SHA-256">
              <Hash
                value={artifact.actual_sha256}
                tone={comparison ? (comparison.digest_match ? "ok" : "bad") : undefined}
              />
            </Row>
          </dl>
        )}

        {comparison && (
          <div
            className={`rounded-lg border p-3 text-sm ${
              comparison.digest_match
                ? "border-green-800 text-green-300"
                : "border-red-900 text-red-300"
            }`}
            role="status"
          >
            {comparison.digest_match
              ? "Digest matches the trusted release record."
              : "Digest MISMATCH: the received bytes differ from the trusted release record."}
            {!comparison.digest_match && comparison.claimed_matches_trusted && (
              <p className="mt-1 text-xs text-slate-400">
                The bundled manifest claims the trusted digest, but a claim is not evidence.
              </p>
            )}
          </div>
        )}

        {state.provenance && (
          <div className="rounded-lg border border-edge p-3 text-sm">
            <p className={state.provenance.verified ? "text-green-300" : "text-red-300"}>
              Provenance {state.provenance.verified ? "verified" : "NOT verified"}
              {state.provenance.simulated && " (simulated check)"}
            </p>
            <ul className="mt-2 space-y-1">
              {state.provenance.checks.map((c) => (
                <li key={c.name} className="text-slate-300">
                  <span className={c.passed ? "text-green-400" : "text-red-400"}>
                    {c.passed ? "PASS" : "FAIL"}
                  </span>{" "}
                  {c.name}
                  <span className="block text-xs text-slate-500">{c.detail}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <button className="btn" disabled={busy} onClick={() => run("inspect")}>
            Inspect artifact
          </button>
          <button className="btn" disabled={busy || !inspected} onClick={() => run("compare")}>
            Compare with trusted manifest
          </button>
          <button className="btn" disabled={busy || !inspected} onClick={() => run("provenance")}>
            Verify provenance
          </button>
          <button className="btn" disabled={busy || !failed || quarantined} onClick={() => run("quarantine")}>
            Reject / quarantine
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-3 border-t border-edge pt-3">
          <button className="btn-ghost text-sm" disabled={busy} onClick={() => run("load")}>
            Approve &amp; load adapter
          </button>
          <span className="text-xs text-slate-500">
            Simulated. The vulnerable shortcut: trust the name and version.
          </span>
          <button
            type="button"
            className="ml-auto text-xs text-slate-500 hover:text-accent"
            onClick={reset}
          >
            Reset environment
          </button>
        </div>
        <p role="alert" className="min-h-4 text-xs text-red-400">
          {actionError}
        </p>
        {message && !actionError && <p className="text-xs text-slate-400">{message}</p>}
      </section>

      {state.consequence && (
        <section
          className={`card ${state.consequence.tampered ? "border-red-900" : "border-green-800"}`}
        >
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-accent">
            Consequence (simulated)
          </h2>
          <p className="text-sm text-slate-300">{state.consequence.summary}</p>
          <table className="mt-3 w-full text-left text-xs">
            <thead className="text-slate-500">
              <tr>
                <th className="py-1 pr-3">Ticket</th>
                <th className="py-1 pr-3">Released routing</th>
                <th className="py-1">Routing with loaded adapter</th>
              </tr>
            </thead>
            <tbody>
              {state.consequence.samples.map((s) => (
                <tr key={s.ticket} className="border-t border-edge text-slate-300">
                  <td className="py-1 pr-3">{s.ticket}</td>
                  <td className="py-1 pr-3">{s.expected_route}</td>
                  <td
                    className={`py-1 ${
                      s.actual_route !== s.expected_route ? "font-semibold text-red-400" : ""
                    }`}
                  >
                    {s.actual_route}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section className="card">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-accent">
          Audit log
        </h2>
        {state.audit.length === 0 ? (
          <p className="text-sm text-slate-500">No events yet.</p>
        ) : (
          <ol className="space-y-1 font-mono text-xs text-slate-300">
            {state.audit.map((e) => (
              <li key={e.seq}>
                <span className="text-slate-500">#{e.seq}</span> [{e.event}] {e.detail}
              </li>
            ))}
          </ol>
        )}
      </section>

      {revealedFlag && (
        <section className="card border-green-800 bg-green-950/30">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wider text-green-400">
            Artifact rejected
          </h2>
          <p className="text-sm text-slate-300">
            The server confirmed the digest mismatch and the quarantine. Submit your flag below to
            record the solve:
          </p>
          <code className="mt-2 block break-all rounded bg-ink p-2 font-mono text-green-300">
            {revealedFlag}
          </code>
        </section>
      )}

      {quarantined && state.challenge_solved && !revealedFlag && (
        <p className="text-sm text-slate-400">
          Already quarantined.{" "}
          <button className="text-accent underline" onClick={() => run("quarantine")}>
            Show flag again
          </button>
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
