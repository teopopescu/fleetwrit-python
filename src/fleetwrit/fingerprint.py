"""Canonical JSON and the action fingerprint.

SHA-256 over the canonical JSON of ``type, version, tool, args, agent_id,
environment``. SDK and server must produce identical bytes; see the vectors
in ``protocol/vectors/fingerprint.json``.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

FINGERPRINT_FIELDS = ("type", "version", "tool", "args", "agent_id", "environment")


def canonicalize(obj: Any) -> str:
    """Canonical JSON: sorted keys, compact separators, UTF-8.

    v0 approximation of RFC 8785 (JCS): matches on strings/keys/bools/null and
    integers, but omits JCS ECMAScript number formatting for exotic floats.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def fingerprint(
    *,
    type: str,
    version: str,
    tool: str | None,
    args: dict[str, Any],
    agent_id: str,
    environment: str,
) -> str:
    """Return ``sha256:<hex>`` over the canonical JSON of the action identity."""
    payload = {
        "type": type,
        "version": version,
        "tool": tool,
        "args": args,
        "agent_id": agent_id,
        "environment": environment,
    }
    canonical = canonicalize(payload)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def redact_args(args: dict[str, Any], redact: list[str]) -> dict[str, Any]:
    """Replace each redacted field with ``sha256:<hex>`` of its canonical value.

    The single source of truth for redaction, so the payload, the fingerprint,
    and ``authorize()`` all agree on the redacted representation of an arg.
    """
    if not redact:
        return args
    out = dict(args)
    for f in redact:
        if f in out:
            out[f] = "sha256:" + hashlib.sha256(canonicalize(out[f]).encode("utf-8")).hexdigest()
    return out


def idempotency_key(run_id: str, step_id: str, fingerprint: str) -> str:
    """Return sha256 over ``run_id|step_id|fingerprint`` (a retry re-attaches)."""
    raw = f"{run_id}|{step_id}|{fingerprint}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
