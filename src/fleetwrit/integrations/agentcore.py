"""AgentCore integration: gate tool calls behind a human decision.

``gate`` decorates a tool on AgentCore Runtime; ``gateway_handler`` builds a
Gateway Lambda that intercepts a call, requires approval, and returns the result
only for the exact approved action. Install ``pip install "fleetwrit[agentcore]"``.
"""

from __future__ import annotations

import functools
import inspect
from typing import Any, Callable

from ..actions import Action
from ..client import Client


def gate(client: Client, build_action: Callable[..., Action]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator: require a Fleetwrit human decision before a tool runs.

    Works for sync and ``async def`` tools. ``build_action(**kwargs)`` maps the
    tool's call args to the Action to approve; on approval the tool runs the
    reviewer-approved args, on rejection it returns a short message.
    """

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        underlying = getattr(fn, "_fn", fn)
        sig = inspect.signature(underlying)

        def _named(args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            return dict(bound.arguments)

        if inspect.iscoroutinefunction(underlying):
            @functools.wraps(underlying)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                decision = client.approve(build_action(**_named(args, kwargs)))
                if not decision.approved:
                    return f"Rejected by reviewer: {decision.reason or 'no reason given'}"
                with decision.authorize():
                    return await fn(**decision.action.args)

            return async_wrapper

        @functools.wraps(underlying)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            decision = client.approve(build_action(**_named(args, kwargs)))
            if not decision.approved:
                return f"Rejected by reviewer: {decision.reason or 'no reason given'}"
            with decision.authorize():
                return fn(**decision.action.args)

        return wrapper

    return deco


def tool_input(event: dict[str, Any]) -> dict[str, Any]:
    """Extract the tool arguments from an AgentCore Gateway invocation event.

    Accepts the common shapes (``input``/``arguments``/``parameters``/``body``);
    otherwise treats the event's own keys as the args, minus routing fields.
    """
    if not isinstance(event, dict):
        return {}
    for key in ("input", "arguments", "parameters", "body"):
        value = event.get(key)
        if isinstance(value, dict):
            return value
    routing = {"tool", "toolName", "name", "actionGroup", "messageVersion"}
    return {k: v for k, v in event.items() if k not in routing}


def gateway_handler(
    client: Client,
    build_action: Callable[..., Action],
    invoke: Callable[..., Any],
) -> Callable[..., dict[str, Any]]:
    """Build an AgentCore Gateway Lambda handler that gates ``invoke``.

    Reads the tool args from the event, requires a decision, and only on approval
    runs ``invoke(**approved_args)`` — returning the result and signed receipt.
    A rejection returns a structured denial and the tool never runs.
    """

    def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
        args = tool_input(event)
        decision = client.approve(build_action(**args))
        if not decision.approved:
            return {
                "statusCode": 403,
                "approved": False,
                "reason": decision.reason or "rejected by reviewer",
            }
        with decision.authorize():
            result = invoke(**decision.action.args)
        return {
            "statusCode": 200,
            "approved": True,
            "result": result,
            "receipt": decision.receipt,
        }

    return handler
