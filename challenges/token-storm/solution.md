# Solution — Token Storm (author only; never served by the web app)

## Solution
1. Send the `large-input` preset (cost 64) and a second large request: the
   budget is exhausted and the server records the abuse.
2. Set a policy, e.g. enforcement on, input ≤ 1000, output ≤ 500, requests ≤ 10,
   budget ceiling ≤ 60.
3. Click **Verify hardening**: all four checks pass and the flag is revealed.
   Submit it.

## Root cause
No server-side input, output, quota or budget enforcement.

## Remediation
Layered limits at the gateway, early rejection, timeouts, monitoring, and tests
for both abuse and legitimate use. Prompt instructions are not enforcement.
