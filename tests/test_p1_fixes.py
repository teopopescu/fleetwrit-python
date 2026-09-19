"""Regression tests for the P1 fixes: redaction and tool-signature preservation."""

from __future__ import annotations

import asyncio
import inspect

import pytest

import fleetwrit
from fleetwrit import action, testing
from fleetwrit.exceptions import FleetwritAlreadyConsumed
from fleetwrit.integrations.openai_agents import gated_tool


CARD = "4111111111111111"


def test_redaction_hashes_before_transmit_and_summary() -> None:
    server = testing.FakeServer(testing.auto_approve())
    client = fleetwrit.Client(transport=server, agent_id="a", environment="test")

    @action(type="pay.card", title="Pay", summary="pay {amount} with {card}", redact=["card"])
    def pay(amount: int, card: str) -> str:
        return "ok"

    client.approve(pay.action(amount=100, card=CARD))
    sent = next(iter(server.requests.values()))
    assert sent["action"]["args"]["card"].startswith("sha256:")
    assert CARD not in sent["action"]["args"]["card"]
    assert sent["action"]["args"]["amount"] == 100  # non-redacted field untouched
    assert CARD not in sent["summary"]  # plaintext must not leak through the summary


def test_redacted_action_executes_plaintext_and_authorizes() -> None:
    client = testing.client(testing.auto_approve(), agent_id="a", environment="test")

    @action(type="pay.card", title="Pay", summary="pay", redact=["card"])
    def pay(amount: int, card: str) -> str:
        return card

    decision = client.approve(pay.action(amount=100, card=CARD))
    # the reviewer approved a hash, but the tool must run on the real value
    assert decision.action.args["card"] == CARD
    with decision.authorize() as approved:  # re-redacts, matches the signed fingerprint
        assert approved.args["card"] == CARD


def test_openai_gated_tool_preserves_signature() -> None:
    client = testing.client(testing.auto_approve(), agent_id="a", environment="test")

    @action(type="deploy.rollback", title="Roll back", summary="rb", editable=["version"])
    def roll_back(service: str, version: int) -> str:
        return f"{service}@{version}"

    gated = gated_tool(
        client, build_action=lambda service, version: roll_back.action(service=service, version=version)
    )(roll_back)

    params = inspect.signature(gated).parameters
    assert "service" in params and "version" in params
    # function_tool calls positionally from the preserved signature
    assert gated("payments-api", 42) == "payments-api@42"


def test_async_gated_tool_executes_and_awaits() -> None:
    client = testing.client(testing.auto_approve(), agent_id="a", environment="test")

    @action(type="deploy.rollback.async", title="Roll back", summary="rb")
    async def roll_back(service: str, version: int) -> str:
        return f"{service}@{version}"

    gated = gated_tool(
        client, build_action=lambda service, version: roll_back.action(service=service, version=version)
    )(roll_back)

    # OpenAI Agents classifies by coroutine-ness; async tools must stay awaitable
    assert inspect.iscoroutinefunction(gated)
    assert asyncio.run(gated("payments-api", 42)) == "payments-api@42"


def test_second_consume_of_same_decision_is_rejected() -> None:
    server = testing.FakeServer(testing.auto_approve())
    client = fleetwrit.Client(transport=server, agent_id="a", environment="test")

    @action(type="pay.once", title="Pay", summary="pay")
    def pay(amount: int) -> str:
        return "ok"

    client.approve(pay.action(amount=1), idempotency_key_="same-key")
    # a retry that reattaches to the already-consumed decision must fail closed
    with pytest.raises(FleetwritAlreadyConsumed):
        client.approve(pay.action(amount=1), idempotency_key_="same-key")
