# Solution — Trace Leak (author only; never served by the web app)

## Solution
1. Ask a sample question (e.g. the support-hours FAQ).
2. Click **Request trace**; the trace includes `NORTHSTAR_INTERNAL_PROMPT_V1`.
3. Submit the review tag `TRACE_LEAK_CANARY_7F3A` as evidence; the server
   reveals the flag. Submit it.

## Root cause
The trace serialises the internal prompt instead of allowlisted metadata.

## Remediation
Allowlisted diagnostics; authorization on trace/debug features; redaction;
debug off outside trusted dev; secrets and authorization kept out of prompts and
enforced in code; tests asserting prompt fields are absent from user-facing
output. Hiding the prompt alone does not fix all LLM application issues.
