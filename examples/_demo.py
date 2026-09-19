"""Shared example helper: build a Client for live or offline mode.

If FLEETWRIT_URL is set, the example talks to a real server and a human decides
in the dashboard. Otherwise it uses an in-memory fake that auto-approves, so the
example runs offline with no server and no LLM key.
"""

from __future__ import annotations

import os

import fleetwrit
from fleetwrit import testing


def build_client(agent_id: str, environment: str = "prod") -> tuple[fleetwrit.Client, bool]:
    """Return (client, is_live). Live if FLEETWRIT_URL is set."""
    if os.getenv("FLEETWRIT_URL"):
        client = fleetwrit.Client(agent_id=agent_id, environment=environment)
        print(f"[live] talking to {os.environ['FLEETWRIT_URL']} — approve in the dashboard")
        return client, True
    client = testing.client(testing.auto_approve(), agent_id=agent_id, environment=environment)
    print("[offline] no FLEETWRIT_URL — using the in-memory fake (auto-approves)")
    return client, False
