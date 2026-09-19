"""@action definition, schema derivation, version stability, Money hint."""

from __future__ import annotations

import pytest

from fleetwrit import Money, action
from fleetwrit.actions import Action, ActionDefinition


@action(
    type="refund.issue",
    title="Issue refund",
    risk="high",
    reversible=False,
    queue="finance-ops",
    summary="Refund {amount} to customer on charge {charge}",
    display={"amount": Money(currency_field="currency")},
    editable=["amount"],
)
def issue_refund(charge: str, amount: int, currency: str) -> str:
    return f"re_{charge}"


def test_action_decorator_returns_definition_and_stays_callable() -> None:
    assert isinstance(issue_refund, ActionDefinition)
    assert issue_refund(charge="ch_1", amount=1, currency="gbp") == "re_ch_1"


def test_schema_derivation_from_type_hints() -> None:
    schema = issue_refund.schema
    props = schema["properties"]
    assert props["charge"]["type"] == "string"
    assert props["amount"]["type"] == "integer"
    assert props["currency"]["type"] == "string"
    assert set(schema["required"]) == {"charge", "amount", "currency"}


def test_version_is_stable_and_short() -> None:
    v1 = issue_refund.version
    v2 = issue_refund.version
    assert v1 == v2
    assert len(v1) == 8


def test_version_changes_with_schema() -> None:
    @action(type="x.a", title="A", summary="a")
    def a(x: int) -> None: ...

    @action(type="x.b", title="B", summary="b")
    def b(x: int, y: str) -> None: ...

    assert a.version != b.version


def test_action_factory_builds_bound_action() -> None:
    bound = issue_refund.action(charge="ch_123", amount=400000, currency="gbp")
    assert isinstance(bound, Action)
    assert bound.type == "refund.issue"
    assert bound.version == issue_refund.version
    assert bound.reversible is False
    assert bound.args == {"charge": "ch_123", "amount": 400000, "currency": "gbp"}


def test_money_display_hint_carried_on_action() -> None:
    bound = issue_refund.action(charge="ch_1", amount=1, currency="gbp")
    hint = bound.display["amount"]
    assert isinstance(hint, Money)
    assert hint.currency_field == "currency"


def test_summary_template_renders_over_args() -> None:
    bound = issue_refund.action(charge="ch_9", amount=500, currency="gbp")
    assert bound.rendered_summary() == "Refund 500 to customer on charge ch_9"


def test_missing_arg_is_rejected() -> None:
    with pytest.raises(TypeError):
        issue_refund.action(charge="ch_1", amount=1)


def test_unknown_arg_is_rejected() -> None:
    with pytest.raises(TypeError):
        issue_refund.action(charge="ch_1", amount=1, currency="gbp", extra=True)


def test_undeclared_action_can_be_built_directly() -> None:
    a = Action(type="deploy.rollback", args={"service": "api"})
    assert a.type == "deploy.rollback"
    assert a.version == "0"
