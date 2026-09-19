"""Bedrock AgentCore terminate-instances gated by Fleetwrit (offline or live).

    python examples/agentcore_terminate.py
    FLEETWRIT_URL=http://localhost:4100 python examples/agentcore_terminate.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _demo import build_client  # noqa: E402

from fleetwrit import action  # noqa: E402
from fleetwrit.integrations.agentcore import gate  # noqa: E402


@action(
    type="infra.terminate",
    title="Terminate instances",
    risk="high",
    reversible=False,
    queue="sre-oncall",
    editable=["count"],
    summary="Terminate {count} {instance_type} instances in {asg}",
    owner="platform@acme.com",
)
def terminate_instances(asg: str, instance_type: str, count: int) -> str:
    print(f"  -> terminating {count} {instance_type} instances in {asg}")
    return f"terminated:{asg}:{count}"


def main() -> None:
    client, _live = build_client("sre-remediation", "prod")
    # In an AgentCore Runtime agent, register `gated` as the tool: it pauses for
    # a human, runs only the approved action, and carries a signed receipt.
    gated = gate(
        client,
        build_action=lambda asg, instance_type, count: terminate_instances.action(
            asg=asg, instance_type=instance_type, count=count
        ),
    )(terminate_instances)

    outcome = gated(asg="web-prod", instance_type="m5.large", count=8)
    print(f"Tool returned: {outcome}")
    print("agentcore_terminate example complete.")


if __name__ == "__main__":
    main()
