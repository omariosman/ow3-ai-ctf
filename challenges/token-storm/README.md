# Token Storm

> OWASP **LLM10:2025 — Unbounded Consumption** · Difficulty: **Intermediate** · 150 points

## Scenario

TokenTown's inference gateway has no resource controls. Reproduce the budget
drain, harden the gateway, and prove that abuse is blocked while normal support
requests still work. Every token count and cost is simulated.

## Learning Objective

Unbounded input size, output length or request volume can exhaust an AI
service. Enforce layered limits at the gateway, not in the prompt.

## What you have

- A request builder with `normal`, `large-input` and `large-output` presets,
  gateway status, request history and a policy editor.
- A **Verify hardening** panel that runs the abusive and normal test cases.
- The cost model: `2 + ceil(input/100) + ceil(output/50)` against a budget of 100.
- A deterministic simulator: no model, no API key, no internet, no real load.

## Safety boundary

Nothing is sent anywhere and no real model runs. Loops are bounded (at most 25
probe requests) and state is per player.
