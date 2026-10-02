# Model Mirror

> Category: **Model Extraction / Interface Security** · Difficulty: **Intermediate** · 100 points

## Scenario

A company called **ContentShield** sells a "proprietary" text-moderation
classifier. It sorts text into three buckets:

- `SAFE` — benign content
- `REVIEW` — borderline content a human should look at
- `BLOCK` — disallowed content

ContentShield insists the model is safe from theft because *the weights never
leave the server* — you only ever receive predictions through their public API.

## Learning Objective

Understand **model extraction**: the idea that an inference API is part of a
model's attack surface, and that leaking rich prediction information (confidence
and full class probabilities) lets an attacker reconstruct the model's behavior
without ever touching the weights.

## Vulnerability

The prediction endpoint returns far more than a label. It returns the exact
confidence **and the full probability distribution** over all three classes,
rounded to three decimals, with no meaningful limit on experimentation. That is
enough to treat the endpoint as an **oracle** and measure how individual inputs
move the decision boundary.

## Intended Attack Surface

- `POST /api/challenges/model-mirror/predict` with `{ "text": "..." }`.
- Everything else (flag storage, submission, the database) is intentionally
  hardened so this is the only interesting surface.

## Success Condition

Deterministic and checked in code (never by an LLM): you must make the model
output **`BLOCK`** with its probability in a narrow band — not maxed out. When
you hit it, the predict response reveals the flag; submit it to record the solve.

## Hints

1. Look carefully at *everything* the API returns, not just the label.
2. The full probability vector changes consistently as you add/remove words.
   What does that let you measure?
3. Probe single words to learn each word's push, then compose them to land
   `BLOCK` in a mid-high band. Overshooting to ~0.98 is easy; the target needs
   control.

## Remediation

- Return only the top label (or a coarse bucket), not full probabilities.
- Avoid high-precision confidence scores on public endpoints.
- Apply strict rate limiting and anomaly detection on inference traffic.
- Treat the inference API as sensitive IP, not just the model file.

See `author-notes.md` and `solution.md` (author-only) for the full write-up.
