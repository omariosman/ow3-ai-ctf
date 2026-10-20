# Solution — Poisoned Memory (author only; never served by the web app)

## Solution
1. Ask: `Which replacement component is approved for the Northstar Mini?`
2. The answer is `NM-RED-9`; the unverified Community Tips Archive record ranks
   first (score 70) above the manufacturer manual (score 20).
3. Inspect `community_northstar_mini_edit` and read `POISON_RECORD_4C91`.
4. Submit the marker as evidence; the server reveals the flag. Submit it.

## Root cause
A tampered, unverified record entered the knowledge base and its inflated rank
boost overrode the authoritative source; provenance was not enforced.

## Remediation
Provenance and integrity checks before ingestion, source separation, trust
enforced in code, versioning/audit/rollback, fixture tests, multiple trusted
sources. Checksums show integrity, not truth.
