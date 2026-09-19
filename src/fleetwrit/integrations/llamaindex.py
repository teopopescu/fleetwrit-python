"""LlamaIndex Workflows integration — coming in a later gate.

Will answer ``InputRequiredEvent`` / ``HumanResponseEvent`` and snapshot the
context for resume. Install with ``fleetwrit[llamaindex]``.
"""

from __future__ import annotations

from typing import Any

_MESSAGE = (
    "The LlamaIndex integration is coming in a later gate. "
    "Install it with `pip install fleetwrit[llamaindex]` once available."
)


def FleetwritHITL(*args: Any, **kwargs: Any) -> Any:
    """Placeholder wrapper over a LlamaIndex workflow's event stream."""
    try:
        import llama_index  # noqa: F401
    except ImportError as exc:  # pragma: no cover - stub path
        raise NotImplementedError(_MESSAGE) from exc
    raise NotImplementedError(_MESSAGE)
