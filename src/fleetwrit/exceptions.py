"""Exceptions raised by the Fleetwrit SDK. The SDK never fails open."""

from __future__ import annotations


class FleetwritError(Exception):
    """Base class for every error raised by the Fleetwrit SDK."""


class FleetwritUnavailable(FleetwritError):
    """The server could not be reached; raised after retries (fails closed)."""


class PolicyDenied(FleetwritError):
    """A policy engine returned a ``deny`` verdict for the proposed action."""


class FleetwritExpired(FleetwritError):
    """No decision was made before the request's deadline and ``on_expiry='raise'``.

    Raised so a caller never mistakes an expired request for a human's answer.
    """


class FleetwritAlreadyConsumed(FleetwritError):
    """The decision was already acknowledged; refusing to deliver it twice.

    Enforces exactly-once: a retry with the same idempotency key that reaches an
    already-consumed decision fails here rather than executing the action again.
    """


class FleetwritActionMismatch(FleetwritError):
    """The action about to run differs from the action a human approved.

    Raised by ``Decision.authorize`` when ``decision.action``'s fingerprint no
    longer equals the fingerprint the reviewer signed.
    """
