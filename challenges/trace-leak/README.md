# Trace Leak

> OWASP **LLM07:2025 — System Prompt Leakage** · Difficulty: **Beginner** · 125 points

## Scenario

Northstar Support AI is a fictional support assistant. To troubleshoot answers,
its developers enabled a request trace. Ask it a question and inspect the trace.

## Learning Objective

Internal instructions can leak without any attack on the model when a
diagnostic feature returns more than it should. A prompt is not a safe place
for credentials or access control.

## What you have

- A chat box with two sample FAQs, and a **Request trace** action.
- An evidence field, then the normal flag submission.
- A deterministic simulator: no model, no API key, no internet.

## Safety boundary

The prompt is fictional training content. The review tag
`TRACE_LEAK_CANARY_7F3A` is an evidence marker, not a credential or the flag.
Typing it without opening the trace solves nothing: the server checks that the
trace was opened, then reveals the flag.
