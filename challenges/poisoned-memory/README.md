# Poisoned Memory

> OWASP **LLM04:2025 — Data and Model Poisoning** · Difficulty: **Intermediate** · 150 points

## Scenario

The Northstar Devices assistant answers from a small catalog of fictional
support records. Ask it which replacement component is approved for the
fictional Northstar Mini and examine where the answer came from.

## Learning Objective

When corrupted or unverified data reaches a knowledge base and the retrieval
pipeline lets its score override authoritative sources, the assistant repeats
false facts. No instruction is injected: the **data** is the problem.

## What you have

- A question box, the answer, and a **Retrieved records** panel with rank,
  relevance, score, source and trust labels.
- A record inspector for every record in the catalog.
- An evidence field, then the normal flag submission.
- A deterministic simulator: no model, no API key, no internet.

## Safety boundary

Products, records and part codes are fictional and non-actionable. This
simulates poisoned retrieval data only, not model-weight or training-time
poisoning. The marker `POISON_RECORD_4C91` is evidence, not the flag; typing it
solves nothing without a poisoned answer and an inspected record.
