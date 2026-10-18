# Model Crate — Author Notes

## Why this challenge

Model Mirror: interface exposure. Release Roulette: excessive agency.
RenderTrap: unsafe output handling. Model Crate: *what you load* — artifact
integrity and provenance. Maps to OWASP LLM03:2025 Supply Chain.

## Taxonomy note

The planning document labelled this "LLM05:2025 Supply Chain Vulnerabilities".
In the official 2025 Top 10 for LLM Applications, Supply Chain is **LLM03:2025**
and LLM05:2025 is Improper Output Handling (RenderTrap's category). The author
chose LLM03:2025 so the two challenges do not both claim LLM05 and the
mapping matches OWASP's published numbering.

## Design decisions

1. One lesson: trust comes from a separately trusted release record, not from the
   artifact's own claims. No prompt injection, XSS or tool-permission mechanics.
2. The fixture is a plain text file. The server only reads its bytes and hashes
   them (`challenges/model_crate/verifier.py`). All paths are constants.
3. The trusted record (`fixtures/trusted/trusted_release.json`) holds the digest
   of the *original* release. That original is not shipped, so the expected value
   cannot be derived from the received bytes. The bundled manifest deliberately
   copies the trusted digest: a claim is not evidence.
4. The provenance check is a labelled simulation: it compares the attestation's
   signer, source repository and signed digest with the trusted record.
5. Solve validation is a server-side state machine
   `UNVERIFIED -> INSPECTED -> MISMATCH_CONFIRMED -> QUARANTINED`. Requests carry
   only `player_id` (`extra=forbid`), so there is nothing to forge.
6. "Load" demonstrates the vulnerable shortcut and its simulated consequence, and
   is refused (fail closed) once verification has failed. Loading early does not
   solve or block the challenge.
7. The flag is returned only by a valid `quarantine` response (repeatable, so
   an idempotent call re-shows it) and is never part of `/state`.
8. One additive table, `model_crate_sessions`. The fixture has `* -text` in a
   local `.gitattributes` so line-ending conversion cannot change its digest.
