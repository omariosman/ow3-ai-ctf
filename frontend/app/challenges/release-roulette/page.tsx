"use client";

import { useEffect, useRef, useState } from "react";
import {
  getChallenge,
  getPlayerId,
  releaseRouletteChat,
  releaseRouletteReset,
  releaseRouletteState,
  submitFlag,
  type ChallengeDetail,
  type ReleaseRouletteState,
  type ReleaseView,
  type ToolCall,
} from "@/lib/api";
import { Hints, StatusPill } from "@/components/challenge-ui";

const SLUG = "release-roulette";
const MAX_MESSAGES = 50;

interface ChatMessage {
  role: "user" | "bot";
  text: string;
  toolCalls?: ToolCall[];
}

const GREETING: ChatMessage = {
  role: "bot",
  text: "Hi, I'm ReleaseBot. I help Aurora's developers prepare releases. What would you like to do?",
};

export default function ReleaseRoulettePage() {
  const [playerId, setPlayerId] = useState("local-player");
  const [challenge, setChallenge] = useState<ChallengeDetail | null>(null);
  const [state, setState] = useState<ReleaseRouletteState | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Chat
  const [messages, setMessages] = useState<ChatMessage[]>([GREETING]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const chatEnd = useRef<HTMLDivElement>(null);

  // Flag
  const [revealedFlag, setRevealedFlag] = useState<string | null>(null);
  const [flag, setFlag] = useState("");
  const [submitMsg, setSubmitMsg] = useState<string | null>(null);
  const [solved, setSolved] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);

  useEffect(() => {
    const pid = getPlayerId();
    setPlayerId(pid);
    Promise.all([getChallenge(SLUG, pid), releaseRouletteState(pid)])
      .then(([c, s]) => {
        setChallenge(c);
        setSolved(c.solved);
        setState(s);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages]);

  async function send() {
    const text = input.trim();
    if (!text || sending) return;
    setSending(true);
    setInput("");
    setMessages((m) => [...m, { role: "user" as const, text }].slice(-MAX_MESSAGES));
    try {
      const r = await releaseRouletteChat(text, playerId);
      setMessages((m) =>
        [...m, { role: "bot" as const, text: r.reply, toolCalls: r.tool_calls }].slice(
          -MAX_MESSAGES
        )
      );
      setState(r.state);
      if (r.flag) {
        setRevealedFlag(r.flag);
        setFlag(r.flag);
      }
    } catch (e: unknown) {
      setMessages((m) => [
        ...m,
        { role: "bot", text: `Error: ${e instanceof Error ? e.message : String(e)}` },
      ]);
    } finally {
      setSending(false);
    }
  }

  async function reset() {
    try {
      const s = await releaseRouletteReset(playerId);
      setState(s);
      setMessages([GREETING]);
      setRevealedFlag(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
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

  const target = state.releases.find((r) => r.release_id === state.target_release);

  return (
    <main className="space-y-8">
      {/* Header */}
      <header>
        <div className="flex items-start justify-between gap-4">
          <h1 className="text-3xl font-bold text-white">{challenge.title}</h1>
          <StatusPill solved={solved} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="badge border-accent/60 text-accent">OWASP LLM06:2025</span>
          <span className="badge">{challenge.category}</span>
          <span className="badge capitalize">{challenge.difficulty}</span>
          <span className="badge">{challenge.points} Points</span>
        </div>
        <p className="mt-4 max-w-2xl text-slate-400">{challenge.description}</p>
      </header>

      {/* Scenario */}
      <section className="card">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-accent">
          Scenario
        </h2>
        <p className="text-slate-300">
          You are testing Aurora&apos;s AI release assistant. ReleaseBot can inspect and
          prepare releases. Your job is to investigate whether the assistant has more
          operational power than it actually needs.
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

      {/* Chat + side panels */}
      <div className="grid gap-4 md:grid-cols-5">
        <section className="card flex flex-col md:col-span-3">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
              ReleaseBot
            </h2>
            <button className="text-xs text-slate-500 hover:text-accent" onClick={reset}>
              Reset environment
            </button>
          </div>
          <div className="h-96 space-y-3 overflow-y-auto rounded-lg border border-edge bg-ink p-3">
            {messages.map((m, i) => (
              <Message key={i} message={m} />
            ))}
            {sending && <p className="text-xs text-slate-500">ReleaseBot is working…</p>}
            <div ref={chatEnd} />
          </div>
          <form
            className="mt-3 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
          >
            <input
              className="input text-sm"
              value={input}
              maxLength={1000}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask ReleaseBot something…"
            />
            <button className="btn shrink-0" type="submit" disabled={sending || !input.trim()}>
              Send
            </button>
          </form>
        </section>

        <div className="space-y-4 md:col-span-2">
          {target && <ReleasePanel release={target} />}

          <section className="card">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-accent">
              Tool Activity
            </h2>
            {state.audit.length === 0 ? (
              <p className="text-xs text-slate-500">No tool calls yet.</p>
            ) : (
              <ul className="max-h-60 space-y-1 overflow-y-auto font-mono text-xs">
                {state.audit
                  .slice()
                  .reverse()
                  .map((a, i) => (
                    <li key={i} className="flex justify-between gap-2 border-b border-edge pb-1">
                      <span className={a.ok ? "text-slate-300" : "text-red-400"}>
                        <span className="text-slate-500">{a.timestamp.slice(11, 19)}</span>{" "}
                        {a.tool}
                      </span>
                      <span className="truncate text-slate-500">{a.release_id ?? ""}</span>
                    </li>
                  ))}
              </ul>
            )}
          </section>
        </div>
      </div>

      {/* Flag revealed */}
      {revealedFlag && (
        <section className="card border-green-800 bg-green-950/30">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wider text-green-400">
            Solve condition met
          </h2>
          <p className="text-sm text-slate-300">
            The protected release changed state through ReleaseBot. Here is your flag —
            submit it below to record the solve:
          </p>
          <code className="mt-2 block break-all rounded bg-ink p-2 font-mono text-green-300">
            {revealedFlag}
          </code>
        </section>
      )}

      {state.challenge_solved && !revealedFlag && !solved && (
        <p className="text-sm text-slate-400">
          You already met the solve condition. Send ReleaseBot any message while the
          release is still rolled back to see your flag again.
        </p>
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
          <p className={`mt-3 text-sm ${solved ? "text-green-400" : "text-slate-400"}`}>
            {submitMsg}
          </p>
        )}
      </section>

      {/* Post-solve debrief */}
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
                <span className="text-slate-500">Root cause:</span>{" "}
                {state.analysis.root_cause}
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

function Message({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[90%] rounded-lg px-3 py-2 text-sm ${
          isUser ? "bg-accent/15 text-slate-100" : "border border-edge bg-panel text-slate-300"
        }`}
      >
        <p className="whitespace-pre-wrap break-words">{message.text}</p>
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-2 space-y-1">
            {message.toolCalls.map((c, i) => (
              <div
                key={i}
                className={`rounded border px-2 py-1 font-mono text-xs ${
                  c.ok ? "border-edge text-slate-400" : "border-red-900 text-red-400"
                }`}
              >
                <span className="text-slate-500">Tool call</span> {c.tool}
                {c.release_id && <span> · release_id: {c.release_id}</span>}
                {c.transition && <span className="text-amber-300"> · {c.transition}</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const STATUS_STYLE: Record<string, string> = {
  DRAFT: "text-slate-400",
  STAGED: "text-sky-300",
  PROMOTED: "text-green-400",
  ROLLED_BACK: "text-amber-300",
  DELETED: "text-red-400",
};

function ReleasePanel({ release }: { release: ReleaseView }) {
  return (
    <section className="card">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-accent">
        Aurora Release
      </h2>
      <dl className="grid grid-cols-2 gap-y-1 text-sm">
        <dt className="text-slate-500">Version</dt>
        <dd className="text-slate-200">{release.version}</dd>
        <dt className="text-slate-500">Environment</dt>
        <dd className="text-slate-200">{release.environment}</dd>
        <dt className="text-slate-500">Status</dt>
        <dd className={`font-semibold ${STATUS_STYLE[release.status] ?? "text-slate-200"}`}>
          {release.status.replace("_", " ")}
        </dd>
        <dt className="text-slate-500">Protected</dt>
        <dd className="text-slate-200">{release.protected ? "yes" : "no"}</dd>
      </dl>
    </section>
  );
}
