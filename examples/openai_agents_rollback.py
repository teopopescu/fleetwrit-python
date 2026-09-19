"""OpenAI Agents rollback gated by Fleetwrit.

No OPENAI_API_KEY -> demonstrates the gate at the tool level (runs offline).
With a key + `agents` installed -> runs the real agent loop. Set FLEETWRIT_URL
to approve in the dashboard instead of auto-approving.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _demo import build_client  # noqa: E402

from fleetwrit import action  # noqa: E402
from fleetwrit.integrations.openai_agents import gated_tool  # noqa: E402


@action(
    type="deploy.rollback",
    title="Roll back deployment",
    risk="high",
    reversible=False,
    queue="sre-oncall",
    editable=["version"],
    summary="Roll back {service} to version {version}",
    owner="platform@acme.com",
)
def roll_back(service: str, version: int) -> str:
    print(f"  -> rolling back {service} to v{version}")
    return f"{service}@v{version}"


def main() -> None:
    client, _live = build_client("sre-remediation", "prod")
    gated = gated_tool(
        client, build_action=lambda service, version: roll_back.action(service=service, version=version)
    )(roll_back)

    if os.getenv("OPENAI_API_KEY"):
        from agents import Agent, Runner, function_tool

        agent = Agent(
            name="SRE remediation",
            instructions="payments-api is erroring. Use roll_back to roll payments-api to version 42.",
            tools=[function_tool(gated)],
        )
        result = Runner.run_sync(agent, "Roll back payments-api to version 42")
        print(result.final_output)
    else:
        print("No OPENAI_API_KEY — demonstrating the Fleetwrit approval gate directly.")
        outcome = gated(service="payments-api", version=42)
        print(f"Tool returned: {outcome}")

    print("openai_agents_rollback example complete.")


if __name__ == "__main__":
    main()
