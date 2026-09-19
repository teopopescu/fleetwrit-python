"""The Fleetwrit Client: approve, input, choose, task, guard, register."""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Iterator

from .actions import Action, ActionDefinition
from .decision import Decision, Reviewer
from .fingerprint import canonicalize, fingerprint, idempotency_key
from .transport import HttpTransport, Transport


def _apply_redaction(args: dict[str, Any], redact: list[str]) -> dict[str, Any]:
    """Hash redacted fields before they leave the process (never send plaintext)."""
    if not redact:
        return args
    out = dict(args)
    for f in redact:
        if f in out:
            out[f] = "sha256:" + hashlib.sha256(canonicalize(out[f]).encode("utf-8")).hexdigest()
    return out

if TYPE_CHECKING:
    from .policy import Guard, Policy

PROTOCOL_SCHEMA = "fleetwrit/v1"
_DURATION_RE = re.compile(r"^\s*(\d+)\s*([smhd])\s*$")
_DURATION_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_duration(value: str | int) -> int:
    """Parse ``"30m"``, ``"1h"``, ``"7d"`` (or an int of seconds) to seconds."""
    if isinstance(value, int):
        return value
    match = _DURATION_RE.match(value)
    if not match:
        raise ValueError(f"invalid duration: {value!r}")
    return int(match.group(1)) * _DURATION_UNITS[match.group(2)]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Client:
    """Entry point to Fleetwrit. Reads config from env; talks to a transport.

    Env: ``FLEETWRIT_URL``, ``FLEETWRIT_API_KEY``, ``FLEETWRIT_AGENT_ID``,
    ``FLEETWRIT_ENVIRONMENT``. Inject ``transport`` (e.g. from
    ``fleetwrit.testing``) to run with no network.
    """

    def __init__(
        self,
        *,
        url: str | None = None,
        api_key: str | None = None,
        agent_id: str | None = None,
        environment: str | None = None,
        transport: Transport | None = None,
        version: str | None = None,
        run_id: str | None = None,
    ) -> None:
        self.url = url or os.getenv("FLEETWRIT_URL")
        self.api_key = api_key or os.getenv("FLEETWRIT_API_KEY")
        self.agent_id = agent_id or os.getenv("FLEETWRIT_AGENT_ID", "unknown-agent")
        self.environment = environment or os.getenv("FLEETWRIT_ENVIRONMENT", "dev")
        self.version = version
        self.run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
        self._transport = transport or HttpTransport(self.url, self.api_key)
        self._step = 0
        self._definitions: list[ActionDefinition] = []

    # --- registry ----------------------------------------------------------

    def register(self, *definitions: ActionDefinition) -> None:
        """Upload agent metadata and action definitions to the catalog."""
        self._definitions.extend(definitions)
        payload = {
            "agent": self._agent_block(),
            "action_types": [d.definition() for d in self._definitions],
        }
        self._transport.register(payload)

    # --- core calls --------------------------------------------------------

    def approve(
        self,
        action: Action,
        *,
        context: dict[str, Any] | None = None,
        queue: str | None = None,
        expires_in: str | int | None = None,
        on_expiry: str = "reject",
        idempotency_key_: str | None = None,
        run_id: str | None = None,
        parent_request_id: str | None = None,
        trace_id: str | None = None,
    ) -> Decision:
        """Ask a human to approve, approve-with-edits, or reject one action."""
        payload = self._build_request(
            "approve",
            action,
            context=context,
            queue=queue,
            expires_in=expires_in,
            on_expiry=on_expiry,
            idempotency_key_=idempotency_key_,
            run_id=run_id,
            parent_request_id=parent_request_id,
            trace_id=trace_id,
        )
        created = self._transport.create_request(payload)
        request_id = created["id"]
        raw = self._await_decision(request_id, expires_in)
        self._transport.ack(request_id)
        return self._decision_from(raw, fallback_action=action, request_id=request_id)

    def input(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        queue: str | None = None,
        expires_in: str | int | None = None,
        on_expiry: str = "raise",
    ) -> Any:
        """Ask a human for a fact only they have; return the validated value."""
        action = Action(type="input", args={"prompt": prompt, "schema": schema or {}})
        payload = self._build_request(
            "input", action, context=context, queue=queue,
            expires_in=expires_in, on_expiry=on_expiry, summary=prompt,
        )
        created = self._transport.create_request(payload)
        request_id = created["id"]
        raw = self._await_decision(request_id, expires_in)
        self._transport.ack(request_id)
        return raw.get("value")

    def choose(
        self,
        prompt: str,
        options: list[Any],
        *,
        context: dict[str, Any] | None = None,
        queue: str | None = None,
        expires_in: str | int | None = None,
        on_expiry: str = "raise",
    ) -> Any:
        """Ask a human to pick one of 2-6 options; return the chosen option id."""
        action = Action(
            type="choose", args={"prompt": prompt, "options": list(options)}
        )
        payload = self._build_request(
            "choose", action, context=context, queue=queue,
            expires_in=expires_in, on_expiry=on_expiry, summary=prompt,
        )
        created = self._transport.create_request(payload)
        request_id = created["id"]
        raw = self._await_decision(request_id, expires_in)
        self._transport.ack(request_id)
        return raw.get("option")

    @contextmanager
    def task(self, name: str) -> Iterator[None]:
        """Count one agent task, the denominator of the north-star metric."""
        self._transport_safe_task(name, "start")
        try:
            yield
        finally:
            self._transport_safe_task(name, "end")

    def guard(self, *, policy: "Policy") -> "Guard":
        """Wrap execution with a policy engine: allow, deny, or ask a human."""
        from .policy import Guard

        return Guard(self, policy)

    # --- helpers -----------------------------------------------------------

    def _await_decision(self, request_id: str, expires_in: str | int | None) -> dict[str, Any]:
        """Re-poll the long-poll endpoint until a terminal decision or expiry.

        A fake transport returns a terminal outcome immediately; a live server
        returns ``{"outcome": "pending"}`` while a human decides, so we loop.
        """
        import time as _time

        ttl = parse_duration(expires_in) if expires_in is not None else 3600
        deadline = _time.monotonic() + ttl
        while True:
            raw = self._transport.get_decision(request_id, wait=30)
            if raw.get("outcome") not in (None, "pending"):
                return raw
            if _time.monotonic() >= deadline:
                return raw

    def _transport_safe_task(self, name: str, phase: str) -> None:
        record = getattr(self._transport, "record_task", None)
        if callable(record):
            record(name, phase)

    def _agent_block(self) -> dict[str, Any]:
        return {
            "id": self.agent_id,
            "environment": self.environment,
            "version": self.version,
        }

    def _build_request(
        self,
        kind: str,
        action: Action,
        *,
        context: dict[str, Any] | None = None,
        queue: str | None = None,
        expires_in: str | int | None = None,
        on_expiry: str = "reject",
        idempotency_key_: str | None = None,
        run_id: str | None = None,
        parent_request_id: str | None = None,
        trace_id: str | None = None,
        summary: str | None = None,
    ) -> dict[str, Any]:
        self._step += 1
        run = run_id or self.run_id
        step_id = f"step_{self._step}"
        args = _apply_redaction(action.args, getattr(action, "redact", []))
        fp = fingerprint(
            type=action.type, version=action.version, tool=action.tool,
            args=args, agent_id=self.agent_id, environment=self.environment,
        )
        idem = idempotency_key_ or idempotency_key(run, step_id, fp)
        created = _now()
        ttl = parse_duration(expires_in) if expires_in is not None else 3600
        return {
            "schema": PROTOCOL_SCHEMA,
            "kind": kind,
            "agent": self._agent_block(),
            "action": {
                "type": action.type,
                "version": action.version,
                "tool": action.tool,
                "args": args,
                "reversible": action.reversible,
            },
            "fingerprint": fp,
            "summary": summary or action.rendered_summary() or action.title or action.type,
            "context": context or {},
            "queue": queue or action.queue,
            "provenance": {
                "run_id": run,
                "parent_request_id": parent_request_id,
                "trace_id": trace_id,
            },
            "idempotency_key": idem,
            "created_at": _iso(created),
            "expires_at": _iso(created + timedelta(seconds=ttl)),
            "on_expiry": on_expiry,
        }

    def _decision_from(
        self, raw: dict[str, Any], *, fallback_action: Action, request_id: str
    ) -> Decision:
        outcome = raw.get("outcome", "rejected")
        approved = outcome in ("approved", "approved_with_edits")
        modified = outcome == "approved_with_edits"
        action = self._action_from(raw.get("action"), fallback_action)
        reviewer_raw = raw.get("reviewer")
        reviewer = Reviewer(**reviewer_raw) if reviewer_raw else None
        return Decision(
            outcome=outcome,
            approved=approved,
            modified=modified,
            action=action,
            reason=raw.get("reason"),
            reviewer=reviewer,
            receipt=raw.get("receipt"),
            value=raw.get("value"),
            option=raw.get("option"),
            request_id=request_id,
            original_fingerprint=raw.get("original_fingerprint"),
            approved_fingerprint=raw.get("final_fingerprint"),
            _agent_id=self.agent_id,
            _environment=self.environment,
        )

    def _action_from(
        self, data: dict[str, Any] | None, fallback: Action
    ) -> Action:
        if not data:
            return fallback
        return Action(
            type=data.get("type", fallback.type),
            args=data.get("args", fallback.args),
            version=data.get("version", fallback.version),
            tool=data.get("tool", fallback.tool),
            reversible=data.get("reversible", fallback.reversible),
            title=fallback.title,
            summary=fallback.summary,
            risk=fallback.risk,
            queue=fallback.queue,
            editable=list(fallback.editable),
            display=dict(fallback.display),
        )
