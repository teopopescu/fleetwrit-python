"""Regression tests for the P2 fixes: default-binding, display hints, expiry."""

from __future__ import annotations

from datetime import datetime

import pytest

import fleetwrit
from fleetwrit import action, testing
from fleetwrit.actions import Money
from fleetwrit.exceptions import FleetwritExpired


def _client(responder):
    server = testing.FakeServer(responder)
    return server, fleetwrit.Client(transport=server, agent_id="a", environment="test")


def test_action_binds_function_defaults_into_args_and_fingerprint() -> None:
    @action(type="pay.def", title="Pay", summary="pay")
    def pay(amount: int, currency: str = "usd") -> str:
        return currency

    bound = pay.action(amount=100)
    assert bound.args == {"amount": 100, "currency": "usd"}  # default is captured
    # a different effective default must produce a different approval identity
    other = pay.action(amount=100, currency="gbp")
    assert bound.fingerprint("ag", "env") != other.fingerprint("ag", "env")


def test_definition_serializes_display_hints() -> None:
    @action(type="refund.def", title="Refund", summary="r",
            display={"amount": Money(currency_field="currency")})
    def refund(amount: int, currency: str) -> str:
        return "ok"

    assert refund.definition()["display"]["amount"] == {
        "kind": "money", "currency_field": "currency",
    }


def test_action_level_expires_in_propagates() -> None:
    @action(type="t.exp", title="T", summary="s", expires_in="30s")
    def t(x: int) -> int:
        return x

    server, client = _client(testing.auto_approve())
    client.approve(t.action(x=1))
    sent = next(iter(server.requests.values()))
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    delta = (datetime.strptime(sent["expires_at"], fmt) - datetime.strptime(sent["created_at"], fmt)).total_seconds()
    assert 25 <= delta <= 35  # honored the action's 30s default, not the 1h fallback


def test_approve_raises_on_expiry_when_action_declares_raise() -> None:
    @action(type="t.raise", title="T", summary="s", on_expiry="raise")
    def t(x: int) -> int:
        return x

    _, client = _client(testing.scripted([{"outcome": "expired"}]))
    with pytest.raises(FleetwritExpired):
        client.approve(t.action(x=1))


def test_input_raises_on_expiry_by_default() -> None:
    _, client = _client(testing.scripted([{"outcome": "expired"}]))
    with pytest.raises(FleetwritExpired):
        client.input("need a number")
