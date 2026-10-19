# Architecture

A local-first AI Security CTF platform. Two services, one database.

```
┌─────────────────────┐        ┌─────────────────────┐
│   Browser UI        │  HTTP  │   CTF Backend       │
│   (Next.js)         │ ─────▶ │   (FastAPI)         │
│                     │        │                     │
│ Home / Challenges   │        │ Challenge API       │
│ Challenge page      │        │ Submission/Solve    │
│ API console         │        │ Flag validator      │
│ Flag submission     │        │ ┌─────────────────┐ │
└─────────────────────┘        │ │ Model Mirror    │ │
                               │ │ hidden model +  │ │
                               │ │ predict oracle  │ │
                               │ ├─────────────────┤ │
                               │ │ Release Roulette│ │
                               │ │ ReleaseBot agent│ │
                               │ │ + deploy tools  │ │
                               │ └─────────────────┘ │
                               │        │            │
                               │        ▼            │
                               │   SQLite (ORM)      │
                               └─────────────────────┘
```

## Components

### Frontend (`frontend/`)
Next.js App Router + TypeScript + Tailwind. All pages are client components that
call the backend via `lib/api.ts`. The browser owns a local `player_id`
(localStorage) — no auth for the MVP.

### Backend (`backend/app/`)
FastAPI application.

- `main.py` — app factory, CORS, body-size limit, safe error handler, docs
  disabled outside development.
- `config.py` — env-driven settings (prefix `CTF_`).
- `database.py` / `models/` — SQLAlchemy ORM (parameterized queries only).
- `schemas/` — Pydantic request/response validation.
- `routes/challenges.py` — generic list / detail / submit.
- `routes/predict.py` — Model Mirror's inference oracle.
- `routes/release_roulette.py` — Release Roulette chat / state / reset.
- `routes/render_trap.py` — RenderTrap state / summarize / proof / reset.
- `routes/context_hijack.py` — Context Hijack state / ask / reset.
- `routes/model_crate.py` — Model Crate state / inspect / compare / provenance /
  load / quarantine / reset.
- `services/` — registry, seeding, flag generation, flag store, progress.
- `challenges/` — isolated per-challenge code (base class + `model_mirror/`,
  `release_roulette/`, `render_trap/`, `model_crate/`, `context_hijack/`).

### Data model (`models/__init__.py`)
`Challenge`, `Player`, `Submission`, `Solve` (unique per player+challenge), and
`ChallengeProgress` (the deterministic "unlocked" bridge between meeting the
in-challenge condition and retrieving the flag). Release Roulette adds two
challenge-specific tables, `release_roulette_releases` and
`release_roulette_audit`, both scoped by `player_id`. RenderTrap adds one table, `render_trap_sessions`
(last output, preview generation, per-generation nonce), also per player.
Model Crate adds `model_crate_sessions` (verification state machine, evidence
verdicts, audit trail), per player. Its trusted release record and inert
artifact fixture live in `challenges/model_crate/fixtures/`, and the digest is
computed server-side from the fixture bytes.
Context Hijack adds `context_hijack_sessions` (last question, retrieved ids,
simulated response, verdict), per player; its corpus is static in code.

## Flag lifecycle (deterministic solve → explicit submit)

1. Player probes `POST /.../predict` and reaches the solve band (or, for
   Release Roulette, a chat turn leaves the protected release ROLLED_BACK by
   ReleaseBot).
2. Backend marks `ChallengeProgress.unlocked` and returns the flag in that
   response.
3. Player submits the flag via `POST /.../submit`.
4. Backend verifies against the stored **SHA-256** and records a `Solve`.

The plaintext flag lives only in the server-side flag store (`backend/.secrets/`,
or `/data/.secrets` in Docker) — never in Git, the DB, metadata, or the frontend.

## Security posture

ORM-only queries · server-side flag validation · no secrets in frontend/Git ·
env-based config · request size limits · basic rate limiting · structured logs ·
safe error messages · Pydantic validation · explicit CORS. See plan section 23.
