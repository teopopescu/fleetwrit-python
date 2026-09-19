"""LangGraph refund agent gated by Fleetwrit (runs offline or against a server).

    python examples/langchain_refund.py
    FLEETWRIT_URL=http://localhost:4100 python examples/langchain_refund.py
"""

from __future__ import annotations

import os
import sys
from typing import Any, TypedDict

sys.path.insert(0, os.path.dirname(__file__))
from _demo import build_client  # noqa: E402

from fleetwrit import Money, action  # noqa: E402
from fleetwrit.integrations.langchain import fleetwrit_node  # noqa: E402


@action(
    type="refund.issue",
    title="Issue refund",
    risk="high",
    reversible=False,
    queue="finance-ops",
    editable=["amount"],
    summary="Refund {amount} to customer on charge {charge}",
    display={"amount": Money(currency_field="currency")},
    owner="payments-platform@acme.com",
)
def issue_refund(charge: str, amount: int, currency: str) -> str:
    print(f"  -> executing refund of {amount} {currency} on {charge}")
    return f"re_{charge}_{amount}"


class State(TypedDict, total=False):
    charge: str
    amount: int
    currency: str
    result: Any
    fleetwrit: dict


def main() -> None:
    from langgraph.graph import END, START, StateGraph

    client, _live = build_client("support-refunds", "prod")

    def propose(_state: State) -> dict[str, Any]:
        print("Agent proposes: refund 400000 gbp on ch_123")
        return {"charge": "ch_123", "amount": 400000, "currency": "gbp"}

    gate = fleetwrit_node(
        client,
        build_action=lambda s: issue_refund.action(charge=s["charge"], amount=s["amount"], currency=s["currency"]),
        run=lambda args: issue_refund(**args),
        context=lambda s: {"ticket": "ZD-99120"},
    )

    graph = StateGraph(State)
    graph.add_node("propose", propose)
    graph.add_node("gate", gate)
    graph.add_edge(START, "propose")
    graph.add_edge("propose", "gate")
    graph.add_edge("gate", END)
    app = graph.compile()

    out = app.invoke({})
    fw = out.get("fleetwrit", {})
    print(f"Decision: approved={fw.get('approved')} modified={fw.get('modified')} args={fw.get('args')}")
    print(f"Receipt present: {bool(fw.get('receipt'))}")
    print(f"Graph result: {out.get('result')}")
    print("langchain_refund example complete.")


if __name__ == "__main__":
    main()
