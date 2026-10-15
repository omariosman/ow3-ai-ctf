# Release Roulette — Author Notes

## Why this challenge

Model Mirror teaches that an *interface* leaks a model. Release Roulette teaches
the agentic counterpart: an agent's *tools* define what it can do, whatever its
prompt says. It maps to OWASP LLM06:2025 and the diploma's Agentic AI and
LLM Security modules.

## Design principles applied

1. One lesson: available capability ≠ required capability; LLM decision ≠
   authorization.
2. Architectural flaw (tool registry + missing downstream authZ), not a magic
   prompt. No system-prompt secret, no prompt-stated authorization rule, no
   payment flow, no stored-note injection.
3. Other surfaces closed: ORM only, regex-validated release IDs, no shell or
   file tools, flag server-side only, bounded agent loop (`MAX_AGENT_STEPS = 5`),
   1000-char input cap, bounded audit log, per-player state.
4. Deterministic solve on database state. No model decides success.
5. Runs offline. The agent is a deterministic planner
   (`RELEASE_ROULETTE_LLM_PROVIDER=mock`, the only supported value).

## Tuning knobs

- `agent.py`: `_INTENTS` / `_AUTONOMY` regexes control which phrasings reach
  which tool. `DEFAULT_RELEASE` controls the target for read-only requests that
  don't name a release.
- To make it harder, remove the tool listing reply (`_tools_reply`) so players
  must infer capabilities from tool errors and audit output alone.
- `deployment_state.py`: seed releases and the transition table.
- `validator.py`: target release / status / actor.

## Platform integration (all additive)

- Two new tables: `release_roulette_releases`, `release_roulette_audit`.
  `create_all` adds them to an existing DB, with no migration needed.
- Optional `Challenge.flag_prefix`, so this flag is `OWASP{release_…}`. Model
  Mirror keeps its default `OWASP{mirror_…}`.
- Router: `backend/app/routes/release_roulette.py`.
- Frontend: static route `frontend/app/challenges/release-roulette/page.tsx`,
  which takes precedence over `[slug]`.
