"""auto_approve / auto_reject / scripted drive approve() offline."""

from __future__ import annotations

import pytest

from fleetwrit import action, testing


@action(type="refund.issue", title="Refund", summary="Refund {amount}", editable=["amount"])
def issue_refund(charge: str, amount: int, currency: str) -> str:
    return f"re_{charge}"


def _act():
    return issue_refund.action(charge="ch_1", amount=500, currency="gbp")


def test_auto_approve_approves() -> None:
    fw = testing.client(testing.auto_approve())
    decision = fw.approve(_act())
    assert decision.approved
    assert decision.outcome == "approved"
    assert decision.receipt is not None
    assert decision.reviewer is not None


def test_auto_reject_rejects_with_reason() -> None:
    fw = testing.client(testing.auto_reject("policy says no"))
    decision = fw.approve(_act())
    assert not decision.approved
    assert decision.outcome == "rejected"
    assert decision.reason == "policy says no"


def test_scripted_consumes_replies_in_order() -> None:
    fw = testing.client(
        testing.scripted(
            [
                {"outcome": "approved"},
                {"outcome": "rejected", "reason": "second one denied"},
            ]
        )
    )
    first = fw.approve(_act())
    second = fw.approve(_act())
    assert first.approved
    assert not second.approved and second.reason == "second one denied"


def test_scripted_runs_out() -> None:
    fw = testing.client(testing.scripted([{"outcome": "approved"}]))
    fw.approve(_act())
    with pytest.raises(AssertionError):
        fw.approve(_act())


def test_input_and_choose_offline() -> None:
    fw = testing.client(
        testing.scripted(
            [
                {"outcome": "answered", "value": "yes"},
                {"outcome": "chosen", "option": "b"},
            ]
        )
    )
    assert fw.input("Proceed?") == "yes"
    assert fw.choose("Pick", ["a", "b", "c"]) == "b"


def test_pytest_fixture_available(fleetwrit_client) -> None:
    decision = fleetwrit_client.approve(_act())
    assert decision.approved


def test_task_counter_records_on_fake() -> None:
    fw = testing.client(testing.auto_approve())
    with fw.task("handle-ticket"):
        pass
    assert ("handle-ticket", "start") in fw._transport.tasks
    assert ("handle-ticket", "end") in fw._transport.tasks
