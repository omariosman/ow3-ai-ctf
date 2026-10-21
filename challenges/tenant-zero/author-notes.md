# Author notes — Tenant Zero

- Distinct from Trace Leak (prompt exposure): the flaw is missing ownership and
  tenant checks around stored conversations. Closest code pattern: Token Storm.
- One policy drives all three surfaces in `simulator.py`. The acting tenant is a
  server constant (`data.ACTING_TENANT`); clients send only an id or search text.
- Evidence recorded server-side: `leak_demonstrated` (a cross-tenant result was
  actually returned) and a `verify` run where all four checks pass. Changing
  the policy voids verification.
- Checks: Beta open and summary denied; search for "contract renewal" returns no
  Beta results; a summary of `conv-1002` has no raw email/account; own
  conversations open and search works with `enforcement_enabled` on.
- Adaptation: the policy is boolean-only, so "block everything" is not
  expressible; the legitimate-access check guards simulator regressions instead.
- Denial is uniform for unknown and foreign ids when ownership is enforced.
