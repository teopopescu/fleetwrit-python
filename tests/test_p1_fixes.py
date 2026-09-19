"""Regression tests for the P1 fixes: redaction and tool-signature preservation."""

from __future__ import annotations

import inspect

import fleetwrit
from fleetwrit import action, testing
from fleetwrit.integrations.openai_agents import gated_tool


def test_redaction_hashes_before_transmit() -> None:
    server = testing.FakeServer(testing.auto_approve())
    client = fleetwrit.Client(transport=server, agent_id="a", environment="test")

    @action(type="pay.card", title="Pay", summary="pay {amount}", redact=["card"])
    def pay(amount: int, card: str) -> str:
        return "ok"

    client.approve(pay.action(amount=100, card="4111111111111111"))
    sent = next(iter(server.requests.values()))
    card = sent["action"]["args"]["card"]
    assert card.startswith("sha256:")
    assert "4111111111111111" not in card
    assert sent["action"]["args"]["amount"] == 100  # non-redacted field untouched


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
