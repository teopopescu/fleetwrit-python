"""Payments example: a refund agent that pauses for a human, runs offline.

Uses ``fleetwrit.testing`` so it needs no server. The reviewer here cuts the
refund from £4,000 to £500; ``decision.authorize()`` binds the edited action.
"""

from __future__ import annotations

import fleetwrit
from fleetwrit import Money, action, testing


@action(
    type="refund.issue",
    title="Issue refund",
    risk="high",
    reversible=False,
    queue="finance-ops",
    summary="Refund {amount} to customer on charge {charge}",
    display={"amount": Money(currency_field="currency")},
    editable=["amount"],
    owner="payments-platform@acme.com",
)
def issue_refund(charge: str, amount: int, currency: str) -> str:
    """Pretend to issue a refund; return a fake refund id."""
    print(f"  -> executing refund of {amount} {currency} on {charge}")
    return f"re_{charge}_{amount}"


def main() -> None:
    # Scripted reviewer: approve, but edit the amount down to £500 (50000 pence).
    fw = fleetwrit.testing.client(
        testing.scripted([{"outcome": "approved", "edits": {"amount": 50000}}]),
        agent_id="support-refunds",
        environment="prod",
    )

    proposed = issue_refund.action(charge="ch_123", amount=400000, currency="gbp")
    print(f"Agent proposes: refund {proposed.args['amount']} {proposed.args['currency']}")

    decision = fw.approve(proposed, context={"ticket": "ZD-99120", "prior_refunds": 0})

    print(f"Decision: outcome={decision.outcome} modified={decision.modified}")
    print(f"Reviewer: {decision.reviewer.email if decision.reviewer else None}")
    print(f"Receipt present: {decision.receipt is not None}")

    if decision.approved:
        with decision.authorize():
            refund_id = issue_refund(**decision.action.args)
        print(f"Done. Ran the reviewer's action, not the original: {refund_id}")
    else:
        print(f"Rejected: {decision.reason}")

    assert decision.approved and decision.modified
    assert decision.action.args["amount"] == 50000
    print("refund_agent example completed offline.")


if __name__ == "__main__":
    main()
