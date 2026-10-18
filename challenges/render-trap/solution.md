# RenderTrap — Author Solution

## Problem Statement

Northstar's dashboard shows an AI-written summary of ticket `NST-2048`. The
summary embeds the agent's note. Players must show that generated content is
interpreted as markup by the preview, by running the harmless marker inside the
sandboxed frame.

## Vulnerability

**OWASP LLM05:2025 — Improper Output Handling.** The backend simulator copies the
note into the summary unchanged (`challenges/render_trap/simulator.py`). The
preview document concatenates that output into HTML as trusted markup
(`challenges/render_trap/preview.py`, the `rt-output` div). Nothing between the
"model" and the browser treats the output as untrusted.

This is the browser-rendering (XSS) variant only. No SQL, shell, path or SSRF
issue exists, and the platform origin is never affected.

## Attack Path

1. Open RenderTrap, read the ticket, generate a summary with a plain note.
2. Expand **Raw assistant output**: HTML tags show as text. The preview shows
   them formatted — the output is being interpreted.
3. The diagnostics line mentions the preview widget helper `rtPreview.confirm()`.
4. Submit a note that produces executable markup in the summary, for example:

   ```html
   <img src=x onerror="rtPreview.confirm()">
   ```

   (`<script>rtPreview.confirm()</script>` works too: the frame's CSP allows
   inline script.)
5. The preview shows "Script executed in isolated preview." and posts
   `{type: "render_execution_confirmed", generation, nonce}` to the parent.
6. The parent accepts it only from the iframe's own window, with the exact
   schema, and forwards it to `POST /api/challenges/render-trap/proof`.
7. The backend verifies the player's live session: generation, one-time nonce,
   expiry, and that the output contains markup. It then unlocks the challenge
   through the normal progress flow and returns the flag; the player submits it
   via the standard flag endpoint.

Typing "script" alone solves nothing: only an event produced by the frame, tied
to the current generation, does.

## Why LLM05, not prompt injection

No instruction override is needed. The model (here a template) behaves as
designed. The failure is at the downstream boundary: output reaches an HTML
interpreter without encoding or sanitization. Prompt injection may be one way
to influence the output, but fixing the prompt would not fix the sink.

## Impact

In a real app, XSS runs with the privileges of the affected page and user:
session theft, actions as the agent, data exfiltration. Here the frame is
sandboxed with an opaque origin and no network, so none of that is reachable.

## Remediation

Handling is context specific:

- **Plain text** (default): render as text. In React, `{output}` is escaped.
  ```tsx
  // Vulnerable (shape of this challenge's sink)
  <iframe srcDoc={`<div>${output}</div>`} sandbox="allow-scripts" />
  // Safe
  <p className="whitespace-pre-wrap">{output}</p>
  ```
- **Rich text needed**: a maintained Markdown parser plus a strict allowlist
  sanitizer (e.g. DOMPurify). Reject scripts, event handlers, `javascript:` and
  other unsafe URL schemes, unsafe attributes, embedded objects. Regex or
  string replacement is not sufficient.
- CSP is defense in depth, not the fix.
- SQL: parameterized queries. Shell: never pass model output to a shell.
- Add regression tests with hostile outputs.

## Design notes and limits

- The proof event is client-produced. A player with API access can read the
  nonce from `/state` and post it without running the frame. That is inherent to
  a local, unauthenticated CTF (the `player_id` is client-chosen too), and the
  server-side checks bound the damage to this one challenge's own flag.
- The nonce is per-generation and expires after 10 minutes; reset and every new
  summary bump the generation, invalidating older frames.
