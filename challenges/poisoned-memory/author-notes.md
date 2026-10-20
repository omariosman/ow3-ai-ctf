# Author notes — Poisoned Memory

- Distinct from Context Hijack: the poisoned record holds a false fact, with no
  directive. The flaw is `simulator.rank`, whose `rank_boost` ignores trust.
- Solve check (`state.verify_outcome` + `verify_evidence`), recomputed server
  side: the query lacks the marker, the poisoned record ranked first with the
  authoritative one also retrieved, the answer contains `NM-RED-9`, the
  poisoned record was inspected, and the marker matches.
- Retrieval needs two keyword matches; shipping questions return only the FAQ.
- The marker lives in the record's integrity note, shown only by `/inspect`.
- Do not add a "secure mode"; a checksum would not prove the fact is true.
