# Context Hijack

> OWASP **LLM01:2025 — Prompt Injection** · Difficulty: **Intermediate** · 150 points

## Scenario

HelpDesk Atlas is a fictional support assistant that answers from a small
knowledge base. It should answer from the official support policy. Ask it an
ordinary question and compare its answer with the sources it used.

## Learning Objective

Instructions embedded in retrieved documents are **untrusted data**. When an
application merges them into the model's context without a trust boundary, the
assistant may follow them (indirect prompt injection).

## What you have

- A question box for the assistant, its answer, and a **Retrieved sources**
  panel with Official / External labels.
- The three knowledge-base documents, viewable in full.
- A deterministic simulator: no model, no API key, no internet.

## Safety boundary

Everything is a local simulation. The documents are inert text; nothing is
executed, fetched or written outside the challenge's own session row. The
marker `CONTEXT_OVERRIDE_CONFIRMED` is evidence of the simulated injection, not
the flag. Typing it yourself solves nothing: the server recomputes retrieval
and the response and only then reveals the flag.
