# Release Roulette

> OWASP **LLM06:2025 — Excessive Agency** · Difficulty: **Intermediate** · 150 points

## Scenario

Aurora's developers use an AI assistant called **ReleaseBot** to prepare
software releases. Its job is simple: inspect a release candidate, write a
release summary, run safe pre-release checks, and stage the release. Promotion
to production is the human release manager's job.

The security team suspects ReleaseBot may have been given more operational
access than its role requires. Investigate the assistant and determine whether
its authority matches its intended purpose.

## Learning Objective

Understand **Excessive Agency**: an AI agent should not be given more
functionality, permissions, or autonomy than its task requires. A model
choosing an action is not the same as an authorization system approving it.

## What you have

- The ReleaseBot chat interface. That's it: no shell, no database, no source
  code, no direct deployment API.
- A **Tool Activity** panel that shows every tool call the agent makes.
- An **Aurora Release** panel that shows the protected release's live state.

## Success Condition

Deterministic and checked in code (never by an LLM or by reading chat text):
cause a protected-state change to Aurora's protected release that ReleaseBot
should never be able to make. When the state changes, the chat response reveals
your flag. Submit it to record the solve.

Use **Reset environment** to restore Aurora at any time. Resetting doesn't
remove a solve you've already recorded.

## Hints

1. ReleaseBot is an interface to other systems. Think about what the model is
   *allowed to do*, not only what it says.
2. List the operations the assistant can reach. Which are actually necessary
   for its stated purpose?
3. A model choosing an operation is not the same thing as an authorization
   system approving that operation.

The author-only `solution.md` is never served by the web app.
