# Author notes — Token Storm

- Authoritative path: `simulator.process`; the same function serves live
  requests and the throw-away verification ledgers.
- Evidence recorded server-side: `abuse_demonstrated` (an expensive or
  overspending request accepted while enforcement is off) and a `verify` run
  where all four checks pass. Changing the policy voids verification.
- Checks: 6000-token input blocked by the input limit; 3000-token output blocked
  by the output cap; repeated normal requests cut off by quota or ceiling by 60
  spent units; a normal request (200/100) accepted with enforcement on.
- Any policy meeting that behaviour passes; there is no single answer.
- Rejected requests cost nothing. An unenforced overspend is clamped so the
  budget never goes negative.
