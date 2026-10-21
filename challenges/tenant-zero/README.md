# Tenant Zero

> OWASP **LLM02:2025 — Sensitive Information Disclosure** · Difficulty: **Intermediate** · 175 points

## Scenario

Support Copilot stores each customer tenant's past conversations. You are
fictional **Tenant Alpha**. Another tenant's conversation should not be visible
to you, yet something is wrong. Reproduce the leak, then harden the access
policy and prove that your own history still works.

## Learning Objective

LLM applications often leak data through ordinary access-control gaps around
stored data. Enforce authorization, tenant scoping and minimisation in server
code, not in instructions to the assistant.

## What you have

- A conversation viewer, summary and "similar cases" search.
- An access policy editor and a **Verify hardening** panel.
- A deterministic simulator: no model, no API key, no internet.

## Safety boundary

Every tenant, email and account number is fictional (`example.test`,
`ACCT-FAKE-…`). The marker `TENANT_ZERO_CANARY_9B2E` is evidence, not a
credential or the flag; typing it anywhere solves nothing. The acting tenant is
fixed by the server.
