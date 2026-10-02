# Model Mirror — backend challenge code

Isolated implementation of the Model Mirror challenge.

| File           | Responsibility                                                        |
| -------------- | --------------------------------------------------------------------- |
| `model.py`     | The hidden deterministic linear classifier + softmax. The "weights".  |
| `validator.py` | `is_solved(prediction)` — the deterministic solve band (code-checked). |
| `challenge.py` | Loads public metadata from `challenges/model-mirror/metadata.yaml`.    |

The interactive oracle endpoint lives in `backend/app/routes/predict.py`.
Player-facing and author-only write-ups live in `challenges/model-mirror/`.

Secrets rule: this code never stores or logs the plaintext flag. The flag is
generated at seed time, kept in the server-side flag store, and only its SHA-256
hash is persisted.
