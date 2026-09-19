"""SRE example: a remediation agent that gates a deploy rollback, runs offline.

Uses a policy guard: the policy asks a human only for production rollbacks, and
``fleetwrit.testing`` auto-approves so it runs with no server.
"""

from __future__ import annotations

from typing import Any

import fleetwrit
from fleetwrit import action, testing
from fleetwrit.policy import Policy, Verdict


@action(
    type="deploy.rollback",
    title="Roll back deployment",
    risk="critical",
    reversible=False,
    queue="platform-sre",
    summary="Roll back {service} to version {version}",
    editable=["version"],
    owner="platform@acme.com",
)
def rollback_deployment(service: str, version: int, environment: str) -> str:
    """Pretend to roll back a service; return a fake change id."""
    print(f"  -> rolling back {service} to v{version} in {environment}")
    return f"chg_{service}_{version}"


class ProductionRollbackPolicy(Policy):
    """Ask a human for production rollbacks; allow everything else."""

    def evaluate(self, action: Any, principal: Any, context: dict[str, Any]) -> Verdict:
        if action.args.get("environment") == "prod":
            return Verdict.ask(queue="platform-sre", expires_in="30m")
        return Verdict.allow()


def main() -> None:
    fw = fleetwrit.testing.client(
        testing.auto_approve(),
        agent_id="sre-remediation",
        environment="prod",
    )
    guard = fw.guard(policy=ProductionRollbackPolicy())

    print("Staging rollback (policy allows, no human needed):")
    guard.run(rollback_deployment, service="payments-api", version=42, environment="staging")

    print("Production rollback (policy asks, human approves):")
    change_id = guard.run(
        rollback_deployment, service="payments-api", version=42, environment="prod"
    )
    print(f"Approved and executed: {change_id}")

    assert change_id == "chg_payments-api_42"
    print("sre_agent example completed offline.")


if __name__ == "__main__":
    main()
