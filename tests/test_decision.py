"""authorize() passes for the approved action, raises on mismatch and edits."""

from __future__ import annotations

import pytest

from fleetwrit import action, testing
from fleetwrit.exceptions import FleetwritActionMismatch


@action(
    type="refund.issue",
    title="Issue refund",
    risk="high",
    reversible=False,
    summary="Refund {amount}",
    editable=["amount"],
)
def issue_refund(charge: str, amount: int, currency: str) -> str:
    return f"re_{charge}_{amount}"


def _client(responder):
    return testing.client(responder, agent_id="support-refunds", environment="prod")


def test_authorize_passes_for_approved_action() -> None:
    fw = _client(testing.auto_approve())
    decision = fw.approve(issue_refund.action(charge="ch_1", amount=500, currency="gbp"))
    assert decision.approved
    with decision.authorize() as approved:
        assert approved.args["amount"] == 500


def test_authorize_raises_on_mismatch_when_action_mutated() -> None:
    fw = _client(testing.auto_approve())
    decision = fw.approve(issue_refund.action(charge="ch_1", amount=500, currency="gbp"))
    decision.action.args["amount"] = 999999  # tamper after approval
    with pytest.raises(FleetwritActionMismatch):
        with decision.authorize():
            pass


def test_authorize_raises_when_not_approved() -> None:
    fw = _client(testing.auto_reject("no"))
    decision = fw.approve(issue_refund.action(charge="ch_1", amount=500, currency="gbp"))
    assert not decision.approved
    with pytest.raises(FleetwritActionMismatch):
        with decision.authorize():
            pass


def test_approve_with_edits_binds_edited_action() -> None:
    fw = _client(testing.scripted([{"outcome": "approved", "edits": {"amount": 50000}}]))
    original = issue_refund.action(charge="ch_123", amount=400000, currency="gbp")
    original_fp = original.fingerprint("support-refunds", "prod")

    decision = fw.approve(original)

    assert decision.approved and decision.modified
    assert decision.action.args["amount"] == 50000
    assert decision.original_fingerprint == original_fp
    assert decision.approved_fingerprint != original_fp

    # authorize passes for the edited action ...
    with decision.authorize() as approved:
        assert approved.args["amount"] == 50000

    # ... and refuses the original £4,000 action.
    decision.action.args["amount"] = 400000
    with pytest.raises(FleetwritActionMismatch):
        with decision.authorize():
            pass
