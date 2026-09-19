"""OpenAI Agents SDK integration: gate a tool behind approve().

Importing needs no `agents` package. ``gated_tool`` wraps a function so an
approval is required before it runs; ``fleetwrit_run`` runs a Runner with the
SDK installed. Install with ``pip install "fleetwrit[openai-agents]"``.
"""

from __future__ import annotations

from typing import Any, Callable

from ..actions import Action
from ..client import Client


def gated_tool(client: Client, build_action: Callable[..., Action]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator: require a Fleetwrit human decision before a tool runs.

    ``build_action(**kwargs)`` returns the Action to approve from the tool's
    call args; on approval the tool runs the reviewer-approved args, on
    rejection it returns a short message the agent can read.
    """

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(**kwargs: Any) -> Any:
            decision = client.approve(build_action(**kwargs))
            if not decision.approved:
                return f"Rejected by reviewer: {decision.reason or 'no reason given'}"
            with decision.authorize():
                return fn(**decision.action.args)

        wrapper.__name__ = getattr(fn, "__name__", "gated_tool")
        wrapper.__doc__ = fn.__doc__
        return wrapper

    return deco


def fleetwrit_run(agent: Any, user_input: str, **kwargs: Any) -> Any:
    """Run an OpenAI Agents ``Runner`` (requires the SDK and a model)."""
    try:
        from agents import Runner
    except ImportError as exc:
        raise ImportError('pip install "fleetwrit[openai-agents]"') from exc
    return Runner.run_sync(agent, user_input, **kwargs)
