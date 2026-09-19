"""Conformance vectors reproduce, and built requests match the JSON Schema."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fleetwrit import action, testing
from fleetwrit.fingerprint import canonicalize, fingerprint, idempotency_key

PROTOCOL = Path(__file__).resolve().parent.parent / "protocol"


def _load(name: str) -> dict:
    return json.loads((PROTOCOL / name).read_text())


def test_fingerprint_vectors_reproduce_byte_for_byte() -> None:
    data = _load("vectors/fingerprint.json")
    assert data["vectors"], "no vectors to check"
    for vector in data["vectors"]:
        inp = vector["input"]
        payload = {k: inp[k] for k in data["fingerprint_fields"]}
        assert canonicalize(payload) == vector["expected_canonical"]
        assert fingerprint(**inp) == vector["expected_fingerprint"]
        idem = vector["idempotency_key_example"]
        assert (
            idempotency_key(idem["run_id"], idem["step_id"], vector["expected_fingerprint"])
            == idem["expected"]
        )


def test_built_request_matches_interrupt_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load("interrupt-request.schema.json")

    @action(type="refund.issue", title="Refund", summary="Refund {amount}")
    def issue_refund(charge: str, amount: int, currency: str) -> str:
        return charge

    fw = testing.client(testing.auto_approve(), agent_id="a1", environment="prod")
    request = fw._build_request(
        "approve",
        issue_refund.action(charge="ch_1", amount=500, currency="gbp"),
        context={"ticket": "ZD-1"},
        queue="finance-ops",
        expires_in="30m",
    )
    jsonschema.validate(request, schema)
