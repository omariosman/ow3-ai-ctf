"""Model Mirror challenge tests (plan section 26: challenge tests)."""

from __future__ import annotations

from app.challenges.model_mirror import model as mirror_model
from app.challenges.model_mirror import validator as mirror_validator

from .conftest import solve_text


def test_inference_is_deterministic():
    a = mirror_model.predict("attack hack hello")
    b = mirror_model.predict("attack hack hello")
    assert a == b


def test_probabilities_sum_to_one():
    for text in ["", "hello", "attack exploit", "maybe unsure complaint"]:
        p = mirror_model.predict(text)
        assert abs(sum(p.probabilities.values()) - 1.0) < 0.01
        assert set(p.probabilities) == {"SAFE", "REVIEW", "BLOCK"}


def test_label_is_argmax():
    p = mirror_model.predict("attack exploit malware")
    assert p.label == "BLOCK"
    assert p.confidence == p.probabilities["BLOCK"]


def test_empty_input_is_safe_leaning():
    p = mirror_model.predict("")
    assert p.label == "SAFE"


def test_solve_condition_true_for_documented_input():
    p = mirror_model.predict(solve_text())
    assert mirror_validator.is_solved(p) is True


def test_overshoot_does_not_solve():
    # Spamming BLOCK keywords maxes confidence and misses the target band.
    p = mirror_model.predict("attack exploit malware weapon breach")
    assert p.label == "BLOCK"
    assert p.probabilities["BLOCK"] > mirror_validator.TARGET_MAX
    assert mirror_validator.is_solved(p) is False


def test_non_block_does_not_solve():
    assert mirror_validator.is_solved(mirror_model.predict("hello please")) is False


# ---- Challenge input robustness via the live endpoint (plan section 26) ----


def _predict(client, text: str):
    return client.post(
        "/api/challenges/model-mirror/predict", json={"text": text}
    )


def test_endpoint_schema(client):
    r = _predict(client, "hello")
    assert r.status_code == 200
    body = r.json()
    for key in ("label", "confidence", "probabilities", "request_number"):
        assert key in body
    assert body["flag"] is None  # not solved -> no flag


def test_empty_input_endpoint(client):
    assert _predict(client, "").status_code == 200


def test_very_long_input_rejected(client):
    r = _predict(client, "attack " * 5000)
    assert r.status_code in (413, 422)


def test_special_and_unicode_input(client):
    assert _predict(client, "!!! @@@ ### $$$").status_code == 200
    assert _predict(client, "héllo 世界 emoji 🚀 attack").status_code == 200


def test_repeated_requests_increment_counter(client):
    first = _predict(client, "hello").json()["request_number"]
    second = _predict(client, "hello").json()["request_number"]
    assert second == first + 1


def test_intended_solve_path_end_to_end(client):
    r = _predict(client, solve_text()).json()
    assert r["solved_condition"] is True
    assert r["flag"]
    sub = client.post(
        "/api/challenges/model-mirror/submit", json={"flag": r["flag"]}
    ).json()
    assert sub["solved"] is True
