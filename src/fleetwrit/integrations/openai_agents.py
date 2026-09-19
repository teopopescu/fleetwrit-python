"""OpenAI Agents SDK integration: gate a tool behind approve().

Importing needs no `agents` package. ``gated_tool`` wraps a function so an
approval is required before it runs; ``fleetwrit_run`` runs a Runner with the
SDK installed. Install with ``pip install "fleetwrit[openai-agents]"``.
"""

from __future__ import annotations

import functools
import inspect
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
        # Unwrap an @action ActionDefinition to its underlying function so the
        # tool's real parameter signature/annotations survive (function_tool
        # reads inspect.signature, which follows __wrapped__ set by functools.wraps).
        underlying = getattr(fn, "_fn", fn)
        sig = inspect.signature(underlying)

        @functools.wraps(underlying)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # function_tool calls positionally from the preserved signature;
            # bind to recover the named args build_action expects.
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            decision = client.approve(build_action(**bound.arguments))
            if not decision.approved:
                return f"Rejected by reviewer: {decision.reason or 'no reason given'}"
            with decision.authorize():
                return fn(**decision.action.args)

        return wrapper

    return deco


def fleetwrit_run(agent: Any, user_input: str, **kwargs: Any) -> Any:
    """Run an OpenAI Agents ``Runner`` (requires the SDK and a model)."""
    try:
        from agents import Runner
    except ImportError as exc:
        raise ImportError('pip install "fleetwrit[openai-agents]"') from exc
    return Runner.run_sync(agent, user_input, **kwargs)
