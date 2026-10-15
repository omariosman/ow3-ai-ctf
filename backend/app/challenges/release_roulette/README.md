# Release Roulette — backend challenge code

Isolated implementation of the Release Roulette challenge (OWASP LLM06:2025).

| File                  | Responsibility                                                              |
| --------------------- | --------------------------------------------------------------------------- |
| `agent.py`            | Deterministic ReleaseBot planner. `AGENT_TOOLS` (the flaw) vs `SAFE_AGENT_TOOLS`. |
| `tools.py`            | The over-broad deploy-ops adapter. Records the actor, never authorizes. |
| `deployment_state.py` | Simulated per-player Aurora releases, transition table, audit log.           |
| `validator.py`        | `is_solved(release)`: aurora-4.8.1 ROLLED_BACK by `releasebot`.              |
| `challenge.py`        | Loads public metadata from `challenges/release-roulette/metadata.yaml`.      |

Endpoints live in `backend/app/routes/release_roulette.py`. Write-ups live in
`challenges/release-roulette/`.

Safety: every operation only mutates this challenge's SQLite rows. No shell, no
files, no network. The plaintext flag is never stored in the DB or logged.
