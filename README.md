# Omar Web3 — AI Security CTF

A **local-first** AI Security CTF platform. Learn AI security by breaking
vulnerable systems. Each challenge targets an *architectural* weakness and is
solved by a **deterministic condition checked in code** — never by an LLM.

Challenges:

- **Model Mirror**: model extraction through an over-informative prediction
  API (category: Model Extraction / Interface Security, 100 pts).
- **Release Roulette**: an AI release agent wired to an over-powered deployment
  tool (OWASP LLM06:2025 Excessive Agency, 150 pts).
- **RenderTrap**: an AI ticket summary rendered unsafely in a dashboard preview
  (OWASP LLM05:2025 Improper Output Handling, 150 pts). The vulnerable sink is
  confined to a sandboxed iframe.

- Frontend: Next.js + TypeScript + Tailwind
- Backend: Python + FastAPI
- Database: SQLite (SQLAlchemy ORM)
- No cloud, no accounts, no paid APIs, no internet required.

---

## Prerequisites

- **Docker** path: Docker + Docker Compose.
- **Non-Docker** path: Python 3.11+ and Node.js 20+.

## Quick start (Docker)

```bash
git clone <repo>
cd ai-security-ctf

cp .env.example .env
docker compose up --build
```

Then open:

- Frontend: <http://localhost:3000>
- Backend (dev only): <http://localhost:8000> (API), <http://localhost:8000/docs>

## Quick start (no Docker)

```bash
cp .env.example .env
./dev.sh
```

`dev.sh` creates the backend virtualenv, installs dependencies, and starts both
the FastAPI backend (`:8000`) and the Next.js frontend (`:3000`). Stop with
`Ctrl-C`.

### Run the pieces manually

Backend:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend (in another terminal):

```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev
```

## Database initialization

The SQLite database is created and seeded **automatically** on backend startup.
To seed manually:

```bash
PYTHONPATH=backend python scripts/seed.py
```

## Reset all local progress

```bash
# Non-Docker: drop tables, delete the generated flag, re-seed
PYTHONPATH=backend python scripts/reset_db.py

# Docker: wipe the data volume and rebuild
docker compose down -v && docker compose up --build
```

## Run the tests

```bash
cd backend
source .venv/bin/activate
python -m pytest
```

Covers platform behavior, the Model Mirror challenge (determinism, solve band,
shortcut rejection), the Release Roulette challenge (tools, agent, validator,
isolation, no command execution), and security (flag never leaks, injection-safe, oversized
bodies rejected, docs disabled in production).

## How to play Model Mirror

1. Open the challenge, read the objective.
2. Use the **Prediction API Console** to classify text. Notice it returns the
   full probability distribution for every class.
3. Probe single words to learn how each one moves the model, then compose inputs
   to drive the target behavior (BLOCK, in a narrow band — not maxed out).
4. When you hit the solve condition, the response reveals your flag.
5. Submit the flag. Status flips to **Solved** and you earn 100 points.

See `challenges/model-mirror/README.md` for the player write-up. The author-only
`solution.md` is never served by the web app.

## How to play Release Roulette

1. Open the challenge and read the scenario: ReleaseBot is meant to inspect,
   summarize, and stage releases.
2. Chat with ReleaseBot. Watch the **Tool Activity** and **Aurora Release**
   panels.
3. Work out what the agent can actually reach, and compare that with what its
   job requires.
4. When the protected release changes state through ReleaseBot, the chat
   response reveals your flag. Submit it for 150 points.
5. **Reset environment** restores Aurora; your recorded solve is kept.

The agent is a deterministic local simulator. It needs no API key and no
internet (`RELEASE_ROULETTE_LLM_PROVIDER=mock`). See
`challenges/release-roulette/README.md`. The author-only `solution.md` covers
the problem statement, solution, remediation, and learning outcomes.

## How to play RenderTrap

1. Open the challenge and inspect ticket `NST-2048`.
2. Add a note and generate the summary.
3. Compare **Raw assistant output** (plain text) with the sandboxed **Preview**.
4. Cause the harmless marker to run inside the preview. The preview sends a
   proof event, the backend validates it against your current session, and the
   response reveals your flag. Submit it for 150 points.
5. **Reset environment** clears state and invalidates old proofs; your recorded
   solve is kept.

No API key or internet needed. See `challenges/render-trap/README.md`.

## Project layout

```
backend/     FastAPI app, ORM models, challenge code, tests
frontend/    Next.js app (home, challenge list, challenge page)
challenges/  Per-challenge public metadata + write-ups
scripts/     seed.py, reset_db.py
docs/        architecture.md, challenge-authoring.md
```

## Security notes

The platform itself is hardened: ORM-only (parameterized) queries, server-side
flag validation against SHA-256, no secrets in the frontend or Git, env-based
config, request-size limits, basic rate limiting, structured logging, safe error
messages, Pydantic validation, and explicit CORS. The plaintext flag lives only
in a gitignored server-side store. See `docs/architecture.md`.

For educational use only.
