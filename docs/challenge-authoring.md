# Challenge Authoring

How to add a new challenge. The platform stays generic — it never needs to know a
challenge's internals.

## 1. Answer the design questions first (plan section 36)

Before writing code, be able to answer: what exactly is the vulnerability, which
component holds it, what attack the player performs, why it works, what other
surfaces you closed, the exact code-checked solve condition, the remediation,
whether an accidental alternative solve exists, and whether it runs
deterministically offline. If you can't, don't build it yet.

## 2. Create the public content

```
challenges/<slug>/
├── metadata.yaml      # public, NO secrets
├── README.md          # player-facing write-up
├── author-notes.md    # author-only
└── solution.md        # author-only (never served by the web app)
```

`metadata.yaml` fields: `slug, title, category, difficulty, points, author,
description, learning_objectives, hints`. The platform loads this for public
metadata (`ModelMirrorChallenge` shows the pattern).

## 3. Implement the backend challenge

```
backend/app/challenges/<slug>/
├── __init__.py
├── challenge.py    # subclass Challenge; load metadata.yaml
├── model.py        # deterministic logic (no external APIs, no internet)
├── validator.py    # is_solved(...) — the deterministic condition
└── README.md
```

Keep it isolated under `challenges/<slug>/`. If the challenge needs its own
interactive endpoint (like Model Mirror's `/predict`), add a router in
`backend/app/routes/` and include it in `main.py`.

## 4. Register it

Add the challenge to `backend/app/services/registry.py`. Seeding will create its
row, generate a flag, store the plaintext in the server-side flag store, and
persist only the SHA-256 hash.

## 5. Rules

- Flag format `OWASP{...}`, generated at init, stored as SHA-256 only.
- Solve condition decided by **code**, never by an LLM, never by inspecting
  natural language.
- Never put the flag in frontend, metadata, DB rows, or player-exposed env vars.
- Prefer small deterministic models so everything runs offline and reproducibly.

## 6. Test it (plan section 26)

Add `backend/tests/test_<slug>.py` covering: determinism, response schema, the
intended solve path, and at least one obvious shortcut that must **fail**
(e.g. keyword spamming, injection). Run `cd backend && python -m pytest`.
