# Model Crate — Author Solution

## Problem Statement

Northstar's classifier uses the adapter `northstar-ticket-adapter` 1.4.2. The
received artifact has the right name and version and a bundled manifest that
claims the approved digest, but the bytes were replaced. The player must show,
from independent evidence, that the artifact cannot be trusted, and quarantine it.

## Vulnerability

**OWASP LLM03:2025 — Supply Chain.** The vulnerable logic finds the artifact by
name, reads the claimed version, assumes it is trusted and loads it, without
comparing it with an independently trusted digest or checking provenance:

```python
# Vulnerable (pseudocode)
artifact = find_by_name("northstar-ticket-adapter", "1.4.2")
load(artifact)                     # trusts filename + version
```

A digest check answers "are these the bytes the release team approved?". It does
not say who published them; signatures and provenance, rooted in a trusted key,
cover that. A digest computed from the received artifact and trusted on its own
proves nothing, and neither does a digest read from the artifact's own manifest.

## Intended Path

1. Read the incident and the release inventory (status `UNVERIFIED`).
2. Compare the **trusted release record** (expected SHA-256
   `0eceb6c4…c7c0cb`) with the **bundled manifest**, which claims the same digest.
3. **Inspect** the artifact. The server hashes the received bytes:
   `e5c9203e…6727`.
4. **Compare**: the actual digest does not match the trusted one, even though the
   bundled manifest claims it does. State: `MISMATCH_CONFIRMED`.
5. Optional: **Verify provenance**. It fails on the source repository
   (`git.northstar-mirror.example/…` vs `git.northstar.example/…`) and on the
   attestation covering a different digest than the received bytes.
6. **Reject / quarantine**. The backend verifies the transition and returns the
   flag through the normal unlock flow.
7. Submit the flag via the standard endpoint.

Clicking **Approve & load** early shows the simulated consequence (fraud-related
tickets routed to `low / auto-close`) but does not solve the challenge. After a
mismatch is confirmed, load is refused.

## Why this is a supply-chain risk

A replaced model, adapter, dataset or dependency changes AI behaviour with no
change to the application's source. Name, version and an artifact's own manifest
are all attacker-controlled once the artifact is.

## Remediation

- Fetch components only from approved sources; pin versions, avoid mutable tags.
- Verify signatures/provenance with trusted keys and policy.
- Compare actual digests with an independently trusted manifest.
- Keep SBOMs / a model-component inventory; scan and review updates.
- Protect build pipelines, release credentials and signing keys; prefer
  reproducible builds.
- Log verification results; keep a rollback procedure.
- Fail closed: never load a component that fails verification.

```python
# Secure (Python sketch, not the challenge's exact code)
trusted = read_release_record()                       # separate trusted source
actual = hashlib.sha256(artifact_bytes).hexdigest()   # computed server-side
if actual != trusted.expected_sha256 or not verify_provenance(artifact, trusted):
    quarantine(artifact)
    audit("rejected", artifact.id)
    raise Rejected                                    # never load
load(artifact)
```

`verify_provenance` is a placeholder for the project's signature verification;
this repository only simulates it.

## Design notes and limits

- The digest comparison is real SHA-256 over fixture bytes. The provenance check
  is simulated (field comparison, no cryptography).
- The trusted record is a repository file standing in for a release registry.
- State is keyed by the client-chosen `player_id`, like the other challenges; a
  local CTF has no authentication. Clients still cannot supply digests, statuses,
  paths or URLs.
