"""Fleetwrit — the independent authorisation record for AI-agent actions.

An agent stops before a consequential action, a human decides, and the agent
resumes on exactly that decision with a signed receipt. Public API: ``Client``,
``action``, ``Action``, ``Money``, ``Decision``, ``guard``, ``task``.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator

from . import exceptions
from .actions import Action, ActionDefinition, Code, Diff, Link, Money, Table, action
from .client import Client
from .decision import Decision, Reviewer
from .exceptions import (
    FleetwritActionMismatch,
    FleetwritAlreadyConsumed,
    FleetwritError,
    FleetwritExpired,
    FleetwritUnavailable,
    PolicyDenied,
)

if TYPE_CHECKING:
    from .policy import Guard, Policy

__version__ = "0.0.1"

_default_client: Client | None = None


def _client() -> Client:
    global _default_client
    if _default_client is None:
        _default_client = Client()
    return _default_client


def guard(*, policy: "Policy") -> "Guard":
    """Wrap execution with a policy engine, using the default env-configured client."""
    return _client().guard(policy=policy)


@contextmanager
def task(name: str) -> Iterator[None]:
    """Count one agent task on the default env-configured client."""
    with _client().task(name):
        yield


__all__ = [
    "Client",
    "action",
    "Action",
    "ActionDefinition",
    "Decision",
    "Reviewer",
    "Money",
    "Diff",
    "Code",
    "Link",
    "Table",
    "guard",
    "task",
    "exceptions",
    "FleetwritError",
    "FleetwritUnavailable",
    "PolicyDenied",
    "FleetwritActionMismatch",
    "FleetwritAlreadyConsumed",
    "FleetwritExpired",
    "__version__",
]
