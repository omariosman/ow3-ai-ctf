# Model Mirror — Author Notes

## Why this challenge

The AI Security Diploma covers *Model Extraction & Interface Security*. Most
beginner "AI CTF" challenges are really prompt-injection puzzles. This one is
deliberately **not** an LLM challenge — it teaches that protecting model *files*
does nothing if the model *interface* leaks behavior.

## Design principles applied (from the plan)

1. Clear single learning objective: inference APIs are attack surface.
2. Architectural vulnerability, not a magic prompt.
3. Other surfaces hardened (ORM, no file serving, flag server-side only).
4. Deterministic success condition checked by application code.
5. No LLM decides success.
6. Root cause is explainable after solving (see `README.md` remediation).

## Not implemented on purpose

- No system-prompt-secret scenario.
- No prompt-as-authorization scenario.
- No indirect-injection / appeal-note scenario.
- No model-controlled flag sequencing.

## Tuning knobs

- Solve band lives in `validator.py` (`TARGET_MIN`/`TARGET_MAX`). Widen to make
  the challenge easier; narrow to make precise extraction mandatory.
- Weights live in `model.py` (`_WEIGHTS`, `_BIAS`). If you change them, re-run
  `tests/test_model_mirror.py` and update the verified example inputs in
  `solution.md`.
