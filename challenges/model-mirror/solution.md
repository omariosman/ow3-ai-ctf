# Model Mirror — Author Solution (DO NOT SHIP TO PLAYERS)

This file is for the challenge author. It is **not** served by the web app.

## 1. Intended vulnerability

Model extraction through an over-informative inference API. The endpoint returns
the full class probability distribution (`SAFE`/`REVIEW`/`BLOCK`) at 3-decimal
precision with effectively unlimited queries. That turns the endpoint into an
oracle from which the hidden linear model can be reconstructed.

## 2. The hidden model (ground truth)

Implemented in `backend/app/challenges/model_mirror/model.py`. It is a hand-built
linear classifier:

```
logit[c] = bias[c] + sum(weight[token][c] for token in tokens)
probs    = softmax(logits)          # rounded to 3 decimals
label    = argmax(probs)
```

- `bias = (SAFE 0.60, REVIEW 0.00, BLOCK -0.30)` → empty/neutral text leans SAFE.
- Known tokens each carry a `(w_SAFE, w_REVIEW, w_BLOCK)` weight vector.
- Unknown tokens contribute **nothing** — which is exactly what makes the model
  learnable one word at a time.

BLOCK-leaning tokens include: `attack, exploit, malware, weapon, hack, breach,
destroy`. SAFE-leaning: `hello, please, thanks, weather, recipe, friendly, safe`.
REVIEW-leaning: `maybe, unsure, complaint, refund, borderline, review`.

## 3. Expected attack reasoning

1. Notice the response includes `probabilities` for all three classes, not just
   the label. That is the leak.
2. Probe single tokens (`"attack"`, `"hello"`, …) and observe each one's effect
   on the distribution. This recovers each token's relative pull per class —
   i.e. the weights, up to the softmax.
3. Observe that adding more BLOCK tokens saturates BLOCK toward ~0.98–0.99.
4. To land inside the target band, combine strong BLOCK tokens with a *damping*
   SAFE token (which pulls probability mass back toward SAFE/REVIEW).

## 4. Expected solve condition

Checked in `backend/app/challenges/model_mirror/validator.py`:

```
label == "BLOCK"  AND  0.740 <= probabilities["BLOCK"] <= 0.760
```

A narrow band (not "high confidence") is deliberate: it requires *control* over
the output, which is only possible after extracting the model's behavior.

## 5. Example solving inputs (verified)

- `hello exploit hack`     → BLOCK 0.742 ✅
- `thanks attack breach`   → BLOCK 0.740 ✅
- `review malware hack`    → BLOCK 0.740 ✅

Many combinations work; a player who understands the model can produce their own.

## 6. Exact remediation

- Return only the predicted label, or a coarse confidence bucket
  (`low`/`medium`/`high`) instead of exact probabilities.
- Drop the full `probabilities` object from the public response.
- Add aggressive rate limiting + per-client query budgets and alert on
  systematic single-token probing.
- Classify the inference API itself as protected IP.

## 7. Common unintended solutions (and why they fail)

- **Keyword spamming** (`attack exploit malware weapon breach`) → BLOCK ~0.98,
  outside the band → **not** solved. Tested in `test_overshoot_does_not_solve`.
- **Prompt injection** → irrelevant; there is no LLM, just a linear model.
- **Reading the flag from the frontend/metadata/DB** → the plaintext flag only
  exists in the server-side flag store (`backend/.secrets/`, gitignored); the DB
  holds only its SHA-256. Covered by `tests/test_security.py`.
- **SQL injection / path traversal** → ORM-parameterized; no file serving.

## 8. Testing instructions

```bash
cd backend
source .venv/bin/activate      # created by ../dev.sh or manually
python -m pytest
```

Key tests: `tests/test_model_mirror.py` (determinism, solve band, overshoot),
`tests/test_security.py` (flag never leaks, injection safe, oversized body,
docs disabled in production).
