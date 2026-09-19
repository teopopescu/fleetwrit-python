"""LangGraph / LangChain integration: gate a node/tool behind approve().

Importing needs no langgraph; you only need it to build the graph. Install with
``pip install "fleetwrit[langchain]"``.
"""

from __future__ import annotations

from typing import Any, Callable

from ..actions import Action
from ..client import Client


def fleetwrit_node(
    client: Client,
    *,
    build_action: Callable[[dict[str, Any]], Action],
    run: Callable[[dict[str, Any]], Any],
    context: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    result_key: str = "result",
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Return a LangGraph node that gates ``run`` behind a human decision.

    ``build_action`` maps graph state to the Action to approve; ``run`` gets the
    approved (possibly edited) args and its result is written to result_key.
    """

    def node(state: dict[str, Any]) -> dict[str, Any]:
        action = build_action(state)
        decision = client.approve(action, context=context(state) if context else None)
        if not decision.approved:
            return {result_key: None, "fleetwrit": {"approved": False, "reason": decision.reason}}
        with decision.authorize():
            output = run(decision.action.args)
        return {
            result_key: output,
            "fleetwrit": {
                "approved": True,
                "modified": decision.modified,
                "args": decision.action.args,
                "receipt": decision.receipt,
                "reviewer": decision.reviewer.email if decision.reviewer else None,
            },
        }

    return node


class FleetwritMiddleware:
    """Wrap tool callables so each call is gated by a Fleetwrit decision."""

    def __init__(self, client: Client) -> None:
        self.client = client

    def wrap(self, build_action: Callable[..., Action], tool: Callable[..., Any]) -> Callable[..., Any]:
        """Return a tool that approves before running, raising on rejection."""

        def gated(**kwargs: Any) -> Any:
            decision = self.client.approve(build_action(**kwargs))
            if not decision.approved:
                raise PermissionError(decision.reason or "rejected by reviewer")
            with decision.authorize():
                return tool(**decision.action.args)

        gated.__name__ = getattr(tool, "__name__", "gated_tool")
        gated.__doc__ = tool.__doc__
        return gated
