"""Fingerprint determinism, key-order independence, idempotency key."""

from __future__ import annotations

from fleetwrit.fingerprint import canonicalize, fingerprint, idempotency_key

BASE = dict(
    type="refund.issue",
    version="a41f09c2",
    tool="stripe.refunds.create",
    agent_id="support-refunds",
    environment="prod",
)


def test_fingerprint_is_deterministic() -> None:
    args = {"charge": "ch_123", "amount": 400000, "currency": "gbp"}
    assert fingerprint(args=args, **BASE) == fingerprint(args=args, **BASE)


def test_fingerprint_has_sha256_prefix_and_length() -> None:
    fp = fingerprint(args={"a": 1}, **BASE)
    assert fp.startswith("sha256:")
    assert len(fp) == len("sha256:") + 64


def test_fingerprint_is_key_order_independent() -> None:
    a = {"charge": "ch_123", "amount": 400000, "currency": "gbp"}
    b = {"currency": "gbp", "amount": 400000, "charge": "ch_123"}
    assert fingerprint(args=a, **BASE) == fingerprint(args=b, **BASE)


def test_fingerprint_changes_with_args() -> None:
    one = fingerprint(args={"amount": 400000}, **BASE)
    two = fingerprint(args={"amount": 50000}, **BASE)
    assert one != two


def test_fingerprint_changes_with_environment() -> None:
    fields = {**BASE}
    prod = fingerprint(args={"amount": 1}, **fields)
    fields["environment"] = "staging"
    staging = fingerprint(args={"amount": 1}, **fields)
    assert prod != staging


def test_canonicalize_sorts_keys_and_is_compact() -> None:
    assert canonicalize({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_idempotency_key_is_deterministic_and_hex() -> None:
    fp = fingerprint(args={"amount": 1}, **BASE)
    key = idempotency_key("run_77", "step_1", fp)
    assert key == idempotency_key("run_77", "step_1", fp)
    assert len(key) == 64
    assert idempotency_key("run_77", "step_2", fp) != key
