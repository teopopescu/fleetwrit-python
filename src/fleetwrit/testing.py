"""Test helpers: drive approvals offline with an in-memory fake server.

``auto_approve()``, ``auto_reject(reason)`` and ``scripted([...])`` build a
responder; :class:`FakeServer` answers with no network. Use :func:`client` or
the ``fleetwrit_client`` pytest fixture.
"""

from __future__ import annotations

import base64
import json
import uuid
from typing import Any, Callable

from .client import Client
from .exceptions import FleetwritAlreadyConsumed
from .fingerprint import fingerprint

Responder = Callable[[dict[str, Any]], dict[str, Any]]

_REVIEWER = {
    "subject": "auto-reviewer",
    "email": "reviewer@fleetwrit.test",
    "name": "Auto Reviewer",
    "issuer": "https://fleetwrit.test",
}


# --- responders ------------------------------------------------------------


def auto_approve() -> Responder:
    """Approve every ``approve`` request; answer input/choose with a default."""

    def respond(request: dict[str, Any]) -> dict[str, Any]:
        kind = request.get("kind")
        if kind == "input":
            return {"outcome": "answered", "value": None}
        if kind == "choose":
            options = request.get("action", {}).get("args", {}).get("options", [])
            return {"outcome": "chosen", "option": options[0] if options else None}
        return {"outcome": "approved"}

    return respond


def auto_reject(reason: str = "rejected by auto_reject") -> Responder:
    """Reject every request with ``reason``."""

    def respond(request: dict[str, Any]) -> dict[str, Any]:
        return {"outcome": "rejected", "reason": reason}

    return respond


def scripted(replies: list[dict[str, Any]]) -> Responder:
    """Consume a list of reply dicts in order (see module for reply shapes)."""
    queue = list(replies)

    def respond(request: dict[str, Any]) -> dict[str, Any]:
        if not queue:
            raise AssertionError("scripted() ran out of replies")
        return queue.pop(0)

    return respond


# --- fake server -----------------------------------------------------------


class FakeServer:
    """In-memory transport that produces signed decisions with no network.

    Recomputes the final fingerprint server-side (including edits) and signs a
    receipt with an ephemeral Ed25519 key.
    """

    def __init__(self, responder: Responder | None = None) -> None:
        self.responder: Responder = responder or auto_approve()
        self.requests: dict[str, dict[str, Any]] = {}
        self.acked: set[str] = set()
        self.registered: list[dict[str, Any]] = []
        self.tasks: list[tuple[str, str]] = []
        self._signing_key = _new_signing_key()

    def register(self, payload: dict[str, Any]) -> None:
        self.registered.append(payload)

    def record_task(self, name: str, phase: str) -> None:
        self.tasks.append((name, phase))

    def create_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_id = payload.get("idempotency_key") or f"req_{uuid.uuid4().hex[:12]}"
        existing = next(
            (
                rid
                for rid, req in self.requests.items()
                if req["idempotency_key"] == payload["idempotency_key"]
            ),
            None,
        )
        if existing is not None:
            return {"id": existing}
        self.requests[request_id] = payload
        return {"id": request_id}

    def get_decision(self, request_id: str, wait: int = 30) -> dict[str, Any]:
        request = self.requests[request_id]
        reply = self.responder(request)
        return self._build_decision(request, reply)

    def ack(self, request_id: str) -> None:
        if request_id in self.acked:
            raise FleetwritAlreadyConsumed(
                f"decision for {request_id} was already consumed"
            )
        self.acked.add(request_id)

    def cancel(self, request_id: str) -> None:
        self.requests.pop(request_id, None)

    def _build_decision(
        self, request: dict[str, Any], reply: dict[str, Any]
    ) -> dict[str, Any]:
        outcome = reply.get("outcome", "rejected")
        base_action = dict(request["action"])
        edits = reply.get("edits")
        if edits:
            outcome = "approved_with_edits"
            base_action["args"] = {**base_action["args"], **edits}
        agent = request["agent"]
        final_fp = fingerprint(
            type=base_action["type"],
            version=base_action["version"],
            tool=base_action.get("tool"),
            args=base_action["args"],
            agent_id=agent["id"],
            environment=agent["environment"],
        )
        decision: dict[str, Any] = {
            "outcome": outcome,
            "action": base_action,
            "original_fingerprint": request["fingerprint"],
            "final_fingerprint": final_fp,
            "reason": reply.get("reason"),
            "reviewer": dict(_REVIEWER),
            "value": reply.get("value"),
            "option": reply.get("option"),
        }
        if outcome in ("approved", "approved_with_edits"):
            decision["receipt"] = self._sign_receipt(request, final_fp, outcome)
        return decision

    def _sign_receipt(
        self, request: dict[str, Any], final_fp: str, outcome: str
    ) -> str:
        header = {"alg": "EdDSA", "typ": "JWT", "kid": "fake-key-1"}
        payload = {
            "request_id": request["idempotency_key"],
            "fingerprint": final_fp,
            "outcome": outcome,
            "sub": _REVIEWER["subject"],
            "iss": _REVIEWER["issuer"],
        }
        signing_input = f"{_b64(header)}.{_b64(payload)}"
        signature = self._signing_key.sign(signing_input.encode("ascii"))
        return f"{signing_input}.{_b64url_bytes(signature)}"


def client(responder: Responder | None = None, **kwargs: Any) -> Client:
    """Return a Client wired to a :class:`FakeServer` (no network)."""
    server = FakeServer(responder)
    kwargs.setdefault("agent_id", "test-agent")
    kwargs.setdefault("environment", "test")
    return Client(transport=server, **kwargs)


# --- crypto + encoding helpers ---------------------------------------------


def _new_signing_key() -> Any:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    return Ed25519PrivateKey.generate()


def _b64(obj: dict[str, Any]) -> str:
    return _b64url_bytes(json.dumps(obj, separators=(",", ":")).encode("utf-8"))


def _b64url_bytes(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


# --- pytest fixture --------------------------------------------------------

try:  # pragma: no cover - only when pytest is installed
    import pytest

    @pytest.fixture
    def fleetwrit_client() -> Client:
        """Pytest fixture: a Client backed by an auto-approving fake server."""
        return client(auto_approve())

except ImportError:  # pragma: no cover
    pass
