# RenderTrap — Author Notes

## Why this challenge

Model Mirror: interface exposure. Release Roulette: excessive agency.
RenderTrap: what happens *after* the model, when output is consumed. Maps to
OWASP LLM05:2025.

## Design decisions

1. One lesson: generated output is untrusted. Prompt injection is deliberately
   not the focus; the deterministic template removes model luck.
2. The unsafe sink exists in one backend function (`render_trap/preview.py`)
   and one frontend component (`components/render-trap-preview.tsx`), used only
   inside a sandboxed iframe (`allow-scripts` only, opaque origin) with a
   network-blocking CSP. The platform CSP/headers are untouched.
3. The proof is a narrow `postMessage` validated by `MessageEvent.source`, strict
   schema, current generation and a per-generation nonce, then re-validated by
   the backend. The parent exposes no other bridge.
4. Flag flow reuses `ChallengeProgress` + flag store, like the other
   challenges. Only one additive table (`render_trap_sessions`) was added.
5. The endpoint is `/summarize` (not `/submit`) because `/{slug}/submit` is the
   generic flag-submission route.
6. The raw output is rendered as text so the player can see the difference.
