# RenderTrap

> OWASP **LLM05:2025 — Improper Output Handling** · Difficulty: **Intermediate** · 150 points

## Scenario

Northstar Support introduced an AI assistant that summarizes customer tickets.
A dashboard previews the generated summary. The preview sometimes behaves
differently from the raw response. Investigate how generated content is
handled, demonstrate the issue safely, and recover the challenge flag.

## Learning Objective

LLM output is **untrusted data**. Before a downstream component interprets it
(a browser, a database, a shell), it must be handled for that specific context.

## What you have

- Fictional ticket `NST-2048` and a note field.
- A deterministic assistant (no model, no API key, no internet).
- A **raw assistant output** panel (always plain text) and a **sandboxed
  preview**. Compare them.

## Safety boundary

Everything is a local simulation. The preview is an iframe with
`sandbox="allow-scripts"` and a CSP that blocks all network access. It has an
opaque origin: it cannot reach this page, cookies, storage, other challenges, or
the platform API. The only visible effect of the exploit is a harmless marker
inside the preview.

## Success Condition

The preview emits a proof event; the backend checks it belongs to your current
preview generation and nonce, then reveals the flag. Submit it for 150 points.
**Reset environment** clears the state and invalidates old proofs; your recorded
solve is kept.

The author-only `solution.md` is never served by the web app.
