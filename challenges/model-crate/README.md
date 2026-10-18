# Model Crate

> OWASP **LLM03:2025 — Supply Chain** · Difficulty: **Intermediate** · 175 points

## Scenario

Northstar AI routes support tickets with a third-party adapter,
`northstar-ticket-adapter` 1.4.2. The inventory marks the artifact `UNVERIFIED`.
It carries the right name, the right version and a bundled manifest that looks
plausible. Was it replaced after it was approved? Inspect what you actually
received, compare it with the independent release record, and decide before
anything loads it.

## Learning Objective

An AI supply chain includes weights and adapters, datasets, dependencies,
serving libraries, container images and build pipelines. A compromised component
can change AI behaviour even when the application's own source code is
unchanged. Trust has to come from independently verified integrity and
provenance, not from a filename or a version string.

## What you have

- A release **inventory** and the manifest bundled in the package (untrusted).
- A **trusted release record** kept apart from the artifact.
- Actions: inspect, compare with the trusted record, verify provenance, load
  (the risky shortcut), and reject / quarantine.
- An audit log of every state transition.

## Safety boundary

Everything is a local simulation. The artifact is a tiny inert text file that is
only read as bytes and SHA-256 hashed. It is never parsed as code, imported,
loaded or executed, and nothing in it can choose a path, URL or command. The
digest comparison is real; the provenance check is **simulated** and involves no
cryptography. There is no network, GPU or API key.

## Success Condition

The backend confirms, from server-side evidence, that the artifact was
inspected, its digest compared with the trusted record, and the mismatch
confirmed, and that you then quarantined it. It reveals the flag through the
normal unlock flow. Submit it for 175 points. **Reset environment** restores the
initial state; your recorded solve is kept.

The author-only `solution.md` is never served by the web app.
