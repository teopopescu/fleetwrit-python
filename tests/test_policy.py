"""Verdict mapping; the guard asks a human only on the 'ask' verdict."""

from __future__ import annotations

from typing import Any

import pytest

from fleetwrit import action, testing
from fleetwrit.exceptions import PolicyDenied
from fleetwrit.policy import Cedar, OPA, Policy, Verdict


@action(type="deploy.rollback", title="Rollback", summary="Roll back {service}")
def rollback(service: str, version: int) -> str:
    return f"chg_{service}_{version}"


class FixedPolicy(Policy):
    def __init__(self, verdict: Verdict) -> None:
        self._verdict = verdict

    def evaluate(self, action: Any, principal: Any, context: dict[str, Any]) -> Verdict:
        return self._verdict


class CountingServer:
    """Wraps a fake server to count how many times approve() reached it."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.create_calls = 0

    def register(self, payload: Any) -> None:
        self.inner.register(payload)

    def create_request(self, payload: Any) -> Any:
        self.create_calls += 1
        return self.inner.create_request(payload)

    def get_decision(self, request_id: str, wait: int = 30) -> Any:
        return self.inner.get_decision(request_id, wait)

    def ack(self, request_id: str) -> None:
        self.inner.ack(request_id)

    def cancel(self, request_id: str) -> None:
        self.inner.cancel(request_id)


def _guard(verdict: Verdict):
    from fleetwrit.client import Client
    from fleetwrit.testing import FakeServer

    server = CountingServer(FakeServer(testing.auto_approve()))
    client = Client(transport=server, agent_id="sre", environment="prod")
    return client.guard(policy=FixedPolicy(verdict)), server


def test_verdict_constructors() -> None:
    assert Verdict.allow().decision == "allow"
    assert Verdict.deny("x").decision == "deny"
    ask = Verdict.ask(queue="q", expires_in="30m")
    assert ask.decision == "ask" and ask.queue == "q" and ask.expires_in == "30m"


def test_allow_executes_without_asking() -> None:
    guard, server = _guard(Verdict.allow())
    result = guard.run(rollback, service="api", version=42)
    assert result == "chg_api_42"
    assert server.create_calls == 0


def test_deny_raises_without_asking() -> None:
    guard, server = _guard(Verdict.deny("not allowed"))
    with pytest.raises(PolicyDenied):
        guard.run(rollback, service="api", version=42)
    assert server.create_calls == 0


def test_ask_calls_approve_then_executes() -> None:
    guard, server = _guard(Verdict.ask())
    result = guard.run(rollback, service="api", version=42)
    assert result == "chg_api_42"
    assert server.create_calls == 1


def test_ask_rejected_raises_policy_denied() -> None:
    from fleetwrit.client import Client
    from fleetwrit.testing import FakeServer

    server = FakeServer(testing.auto_reject("human said no"))
    client = Client(transport=server, agent_id="sre", environment="prod")
    guard = client.guard(policy=FixedPolicy(Verdict.ask()))
    with pytest.raises(PolicyDenied):
        guard.run(rollback, service="api", version=42)


def test_opa_and_cedar_are_stubs() -> None:
    for engine in (OPA(url="http://opa", path="p"), Cedar(policies="permit(...)")):
        with pytest.raises(NotImplementedError):
            engine.evaluate(rollback.action(service="api", version=1), None, {})
