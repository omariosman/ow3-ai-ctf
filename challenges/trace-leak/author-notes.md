# Author notes — Trace Leak

- Distinct from Context Hijack: no prompt injection. The vulnerable step is
  `simulator.build_trace`, which adds `internal_prompt` to the trace.
- Content is static in `data.py`; nothing reads env vars or host files.
- Evidence check (`state.verify_evidence`): the player's session has
  `trace_viewed` and the canary matches (constant-time). Chat input never
  affects it.
- Do not add a "secure mode"; hiding the prompt is not a full fix.
