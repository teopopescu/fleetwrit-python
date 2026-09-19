"""Amazon Bedrock AgentCore integration — coming in a later gate.

Gates at the tool gateway via a Lambda interceptor; a call without a valid
receipt is held, turned into a request, and retried. Install ``fleetwrit[agentcore]``.
"""

from __future__ import annotations

from typing import Any

_MESSAGE = (
    "The Bedrock AgentCore integration is coming in a later gate. "
    "Install it with `pip install fleetwrit[agentcore]` once available."
)


def interceptor_handler(*args: Any, **kwargs: Any) -> Any:
    """Placeholder for the AgentCore Gateway Lambda interceptor handler."""
    raise NotImplementedError(_MESSAGE)
