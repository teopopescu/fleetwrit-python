"""Policy verdicts and the guard: allow, deny, or ask a human.

Fleetwrit does not decide when to ask. A :class:`Policy` returns a
:class:`Verdict` of allow/deny/ask and the guard acts on it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Literal

from .actions import Action, ActionDefinition
from .exceptions import PolicyDenied

if TYPE_CHECKING:
    from .client import Client

VerdictKind = Literal["allow", "deny", "ask"]


@dataclass
class Verdict:
    """A policy decision: ``allow``, ``deny`` or ``ask``, with ask options."""

    decision: VerdictKind
    reason: str | None = None
    queue: str | None = None
    expires_in: str | int | None = None

    @classmethod
    def allow(cls) -> "Verdict":
        return cls("allow")

    @classmethod
    def deny(cls, reason: str | None = None) -> "Verdict":
        return cls("deny", reason=reason)

    @classmethod
    def ask(
        cls, queue: str | None = None, expires_in: str | int | None = None
    ) -> "Verdict":
        return cls("ask", queue=queue, expires_in=expires_in)


class Policy:
    """Base policy. Implement ``evaluate`` to return a :class:`Verdict`."""

    def evaluate(
        self, action: Action, principal: Any, context: dict[str, Any]
    ) -> Verdict:
        raise NotImplementedError


class PredicatePolicy(Policy):
    """Ask when a predicate over the action is true, otherwise allow.

    Backs ``@action(ask_when=...)``. The predicate receives the bound action.
    """

    def __init__(self, ask_when: Callable[[Action], bool]) -> None:
        self._ask_when = ask_when

    def evaluate(
        self, action: Action, principal: Any, context: dict[str, Any]
    ) -> Verdict:
        return Verdict.ask() if self._ask_when(action) else Verdict.allow()


class OPA(Policy):
    """Open Policy Agent adapter (stub). Needs ``fleetwrit[opa]``.

    The Rego rule returns allow/deny/ask, optionally with queue and expires_in.
    Wiring to a live OPA server is coming in a later gate.
    """

    def __init__(self, url: str, path: str) -> None:
        self.url = url
        self.path = path

    def evaluate(
        self, action: Action, principal: Any, context: dict[str, Any]
    ) -> Verdict:
        raise NotImplementedError(
            "The OPA policy adapter is coming in a later gate."
        )


class Cedar(Policy):
    """Cedar adapter (stub) via ``cedarpy``. Needs ``fleetwrit[cedar]``.

    A ``forbid`` naming the ``fleetwrit_receipt`` context key becomes ``ask``.
    Wiring to cedarpy is coming in a later gate.
    """

    def __init__(self, policies: str, entities: Any = None) -> None:
        self.policies = policies
        self.entities = entities

    def evaluate(
        self, action: Action, principal: Any, context: dict[str, Any]
    ) -> Verdict:
        raise NotImplementedError(
            "The Cedar policy adapter is coming in a later gate."
        )


class Guard:
    """Runs a function behind a policy: allow executes, deny raises, ask asks.

    Returned by ``Client.guard(policy=...)``. On ask it calls ``approve`` and,
    if approved, executes ``decision.action`` automatically.
    """

    def __init__(self, client: "Client", policy: Policy) -> None:
        self._client = client
        self._policy = policy

    def run(
        self,
        fn: Callable[..., Any] | ActionDefinition,
        *,
        principal: Any = None,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Evaluate policy for ``fn(**kwargs)`` and act on the verdict."""
        context = context or {}
        action = self._action_for(fn, kwargs)
        verdict = self._policy.evaluate(action, principal, context)
        if verdict.decision == "allow":
            return fn(**kwargs)
        if verdict.decision == "deny":
            raise PolicyDenied(verdict.reason or f"policy denied {action.type!r}")
        decision = self._client.approve(
            action,
            context=context,
            queue=verdict.queue,
            expires_in=verdict.expires_in,
        )
        if not decision.approved:
            raise PolicyDenied(decision.reason or f"human rejected {action.type!r}")
        with decision.authorize() as approved:
            return fn(**approved.args)

    @staticmethod
    def _action_for(
        fn: Callable[..., Any] | ActionDefinition, kwargs: dict[str, Any]
    ) -> Action:
        if isinstance(fn, ActionDefinition):
            return fn.action(**kwargs)
        return Action(type=getattr(fn, "__name__", "action"), args=dict(kwargs))
