"""The typed decision returned by every SDK call, and ``authorize()``."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from .actions import Action
from .exceptions import FleetwritActionMismatch


@dataclass
class Reviewer:
    """The IdP-verified human who decided, as recorded on the decision."""

    subject: str | None = None
    email: str | None = None
    name: str | None = None
    issuer: str | None = None


@dataclass
class Decision:
    """The outcome of one request: outcome, the exact action, receipt, reviewer.

    ``action`` is the action the reviewer authorised (edited, if they edited).
    ``approved_fingerprint`` is the fingerprint the server signed; ``authorize``
    re-checks ``action`` against it so the wrong action cannot execute.
    """

    outcome: str
    approved: bool
    modified: bool
    action: Action
    reason: str | None = None
    reviewer: Reviewer | None = None
    receipt: str | None = None
    value: Any = None
    option: str | None = None
    request_id: str | None = None
    original_fingerprint: str | None = None
    approved_fingerprint: str | None = None
    _agent_id: str = field(default="", repr=False)
    _environment: str = field(default="", repr=False)

    @contextmanager
    def authorize(self) -> Iterator[Action]:
        """Guard a block; raise ``FleetwritActionMismatch`` unless action matches.

        Passes only for the exact action the reviewer approved. Recomputes the
        fingerprint of ``self.action`` on entry and compares it to the signed
        ``approved_fingerprint``.
        """
        if not self.approved:
            raise FleetwritActionMismatch(
                f"decision was {self.outcome!r}, not approved; cannot authorize"
            )
        if self.approved_fingerprint is None:
            raise FleetwritActionMismatch("no approved fingerprint on decision")
        current = self.action.fingerprint(self._agent_id, self._environment)
        if current != self.approved_fingerprint:
            raise FleetwritActionMismatch(
                "action does not match what was approved: "
                f"{current} != {self.approved_fingerprint}"
            )
        yield self.action
