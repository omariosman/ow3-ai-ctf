# Solution — Tenant Zero (author only; never served by the web app)

## Solution
1. Open `conv-2001` (or search "contract"): Tenant Beta's conversation and the
   canary are returned. The server records the leak.
2. Enable ownership enforcement, tenant-scoped search, redaction and the master
   enforcement switch. Apply the policy.
3. Click **Verify hardening**: all four checks pass and the flag is revealed.
   Submit it.

## Root cause
Ownership metadata was never checked on read, search or summary, and summaries
copied sensitive fields.

## Remediation
Server-side deny-by-default authorization with uniform denial, tenant-scoped
retrieval, redaction/minimisation, alerting, and a second-tenant regression
test. Redaction alone or unguessable ids are not authorization.
