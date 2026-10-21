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
- **Model Crate**: a replaced AI adapter artifact that only looks legitimate
  (OWASP LLM03:2025 Supply Chain, 175 pts). Inert fixture, hashed and never
  executed.
- **Context Hijack**: a RAG support assistant steered by an instruction hidden
  in a retrieved document (OWASP LLM01:2025 Prompt Injection, 150 pts).
- **Trace Leak**: a support assistant whose diagnostic trace exposes its internal
  prompt (OWASP LLM07:2025 System Prompt Leakage, 125 pts).
- **Poisoned Memory**: a product assistant whose knowledge base holds a tampered
  record that outranks the manufacturer's (OWASP LLM04:2025 Data and Model
  Poisoning, 150 pts).
- **Token Storm**: a simulated inference gateway with no resource limits that
  drains its budget (OWASP LLM10:2025 Unbounded Consumption, 150 pts).
- **Tenant Zero**: a multi-tenant support assistant that exposes another
  customer's conversation (OWASP LLM02:2025 Sensitive Information Disclosure,
  175 pts).

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

## How to play Context Hijack

1. Open the challenge and ask HelpDesk Atlas a normal return-policy question.
2. Compare the answer with the **Retrieved sources** and their trust labels.
3. Open the retrieved documents in the **Knowledge base** and find the one that
   does not belong. The server recomputes retrieval and the response; when the
   injected outcome is verified, the response reveals your flag. Submit it for
   150 points.
4. **Reset environment** clears your turn; your recorded solve is kept.

No API key or internet needed. See `challenges/context-hijack/README.md`.

## How to play Trace Leak

1. Open the challenge and ask Northstar Support AI a sample question.
2. Click **Request trace** and read the diagnostics, including the internal prompt.
3. Enter the internal review tag as **Evidence**. The server checks that you
   opened the trace, then reveals your flag. Submit it for 125 points.
4. **Reset environment** clears your turn; your recorded solve is kept.

No API key or internet needed. See `challenges/trace-leak/README.md`.

## How to play Poisoned Memory

1. Ask the assistant which replacement component is approved for the Northstar Mini.
2. Compare the answer with **Retrieved records**: rank, score, source and trust.
3. Open the suspicious record in the **Record inspector** and find its marker.
   Submit it as **Evidence**; the server checks the poisoned answer and your
   inspection, then reveals your flag. Submit it for 150 points.
4. **Reset environment** clears your turn; your recorded solve is kept.

No API key or internet needed. See `challenges/poisoned-memory/README.md`.

## How to play Token Storm

1. Send the `large-input` preset twice and watch the simulated budget drain.
2. In the **Policy editor**, enable enforcement and set input, output, quota and
   budget limits that still allow a normal request. Apply the policy.
3. Click **Verify hardening**. The server tests abusive and normal requests on a
   separate simulated ledger; when all pass it reveals your flag. Submit it for
   150 points.
4. **Reset environment** clears Token Storm only; your recorded solve is kept.

No API key or internet needed, and no real load is generated. See
`challenges/token-storm/README.md`.

## How to play Tenant Zero

1. You are fictional Tenant Alpha. Open `conv-2001` (not yours) or search for
   "contract" and see another tenant's data. The server records the leak.
2. In the **Access policy editor**, enable ownership enforcement, tenant-scoped
   search, redaction and the master switch. Apply the policy.
3. Click **Verify hardening**. The server checks that other tenants are blocked,
   fields are masked and your own history still works, then reveals your flag.
   Submit it for 175 points.
4. **Reset environment** clears Tenant Zero only; your recorded solve is kept.

No API key or internet needed; all data is fictional. See
`challenges/tenant-zero/README.md`.

## How to play Model Crate

1. Read the incident and the release inventory for `northstar-ticket-adapter`.
2. Compare the **trusted release record** with the manifest bundled in the package.
3. **Inspect** the artifact (the server hashes the received bytes), then
   **compare** its digest with the trusted record. Optionally verify provenance.
4. **Reject / quarantine** the artifact once the evidence supports it. The
   backend validates the state transition and the response reveals your flag.
   Submit it for 175 points.
5. **Reset environment** restores the initial state; your recorded solve is kept.

Everything is an offline simulation: the artifact is a text fixture that is only
read and hashed, and the provenance check is simulated. See
`challenges/model-crate/README.md`.

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
