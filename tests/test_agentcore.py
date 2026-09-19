"""Tests for the Amazon Bedrock AgentCore integration."""

from __future__ import annotations

from fleetwrit import action, testing
from fleetwrit.integrations.agentcore import gate, gateway_handler, tool_input


@action(type="deploy.rollback", title="Roll back", summary="rb", editable=["version"])
def roll_back(service: str, version: int) -> str:
    return f"{service}@{version}"


def _build(service, version):
    return roll_back.action(service=service, version=version)


def test_gate_runs_on_approval() -> None:
    client = testing.client(testing.auto_approve(), agent_id="a", environment="test")
    gated = gate(client, build_action=_build)(roll_back)
    assert gated("payments-api", 42) == "payments-api@42"  # positional, like a tool runtime


def test_gate_blocks_on_reject() -> None:
    client = testing.client(testing.auto_reject("policy says no"), agent_id="a", environment="test")
    gated = gate(client, build_action=_build)(roll_back)
    assert "Rejected by reviewer" in gated("payments-api", 42)


def test_gateway_handler_approved_runs_tool_with_receipt() -> None:
    client = testing.client(testing.auto_approve(), agent_id="a", environment="test")
    invoked: list[tuple] = []

    def invoke(service: str, version: int) -> str:
        invoked.append((service, version))
        return f"{service}@{version}"

    handler = gateway_handler(client, build_action=_build, invoke=invoke)
    resp = handler({"tool": "roll_back", "input": {"service": "payments-api", "version": 42}})
    assert resp["statusCode"] == 200 and resp["approved"] is True
    assert resp["result"] == "payments-api@42" and resp["receipt"]
    assert invoked == [("payments-api", 42)]


def test_gateway_handler_rejected_does_not_run_tool() -> None:
    client = testing.client(testing.auto_reject("no"), agent_id="a", environment="test")
    ran: list[int] = []

    def invoke(service: str, version: int) -> str:
        ran.append(1)
        return "ran"

    handler = gateway_handler(client, build_action=_build, invoke=invoke)
    resp = handler({"input": {"service": "x", "version": 1}})
    assert resp["statusCode"] == 403 and resp["approved"] is False and not ran


def test_tool_input_accepts_common_shapes() -> None:
    assert tool_input({"input": {"a": 1}}) == {"a": 1}
    assert tool_input({"arguments": {"b": 2}}) == {"b": 2}
    assert tool_input({"parameters": {"c": 3}}) == {"c": 3}
    assert tool_input({"tool": "roll_back", "service": "x", "version": 1}) == {"service": "x", "version": 1}
