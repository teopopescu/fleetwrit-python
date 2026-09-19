# Fleetwrit Python SDK

**The independent authorisation record for consequential AI-agent actions.**

An agent stops before a consequential action, a named human decides, and the
agent resumes on exactly that decision with a signed receipt — a record that is
tamper-evident and lives outside the system being governed.

This is `fleetwrit-python`, the SDK. The server and dashboard live in the
separate [`fleetwrit`](https://github.com/teopopescu/fleetwrit) repository. This
is an **alpha**: the SDK surface, the fingerprint, action definitions, the policy
hook, the testing helpers and the CLI are implemented and tested, the live HTTP
transport works against the Fleetwrit server, and the **LangGraph** and **OpenAI
Agents** integrations are real and covered by tests. The LlamaIndex/AgentCore
adapters and the OPA/Cedar policy engines are still stubs marked "coming in a
later gate".

## Install

Until the first PyPI release, install from GitHub:

```bash
pip install "git+https://github.com/teopopescu/fleetwrit-python.git"
```

Once published, this becomes:

```bash
pip install fleetwrit
```

Extras pull in framework integrations and policy engines:

```bash
pip install "fleetwrit[langchain]"   # or [llamaindex], [openai-agents], [agentcore]
pip install "fleetwrit[opa]"         # or [cedar]
pip install "fleetwrit[dev]"         # pytest, hypothesis, jsonschema
```

## Run the local stack

The `dev-server` extra pulls in the local server with the dashboard bundled in,
so one install and one command bring up the whole thing — no repo checkout, no
Docker, no Node:

```bash
pip install "fleetwrit[dev-server] @ git+https://github.com/teopopescu/fleetwrit-python.git"
fleetwrit dev            # server API + dashboard on http://localhost:4100
```

Flags: `--port`, `--no-dashboard`, `--no-seed`.

## The three calls and a guard

```python
import fleetwrit
from fleetwrit import action, Money

@action(
    type="refund.issue",
    title="Issue refund",
    risk="high",
    reversible=False,
    queue="finance-ops",
    summary="Refund {amount} to customer on charge {charge}",
    display={"amount": Money(currency_field="currency")},
    editable=["amount"],
)
def issue_refund(charge: str, amount: int, currency: str) -> str:
    ...  # your Stripe call

fw = fleetwrit.Client()  # reads FLEETWRIT_URL, FLEETWRIT_API_KEY, ...

decision = fw.approve(
    issue_refund.action(charge="ch_123", amount=400000, currency="gbp"),
    context={"ticket": "ZD-99120"},
)

if decision.approved:
    with decision.authorize():           # passes only for the approved action
        issue_refund(**decision.action.args)
else:
    print(decision.reason)
```

| Call | Use |
| --- | --- |
| `approve(action, ...)` | Yes / yes-with-edits / no on one exact action |
| `input(prompt, schema=...)` | A fact only a human has |
| `choose(prompt, options)` | Pick one of 2–6 candidate actions |
| `decision.authorize()` | Context manager; blocks if the action no longer matches |
| `fw.task(name)` | Counts agent tasks (the north-star denominator) |
| `fw.guard(policy=...)` | Ask a policy engine first, a human only if told to |

## Configuration

`FLEETWRIT_URL`, `FLEETWRIT_API_KEY`, `FLEETWRIT_AGENT_ID`,
`FLEETWRIT_ENVIRONMENT`. Keys are scoped to one agent and one environment.

## Testing your agent offline

`fleetwrit.testing` runs an in-memory fake server so you can test approval
paths with no network and no reviewer:

```python
from fleetwrit import testing

fw = testing.client(testing.auto_approve())
decision = fw.approve(issue_refund.action(charge="ch_1", amount=500, currency="gbp"))
assert decision.approved

# also: testing.auto_reject("nope"), testing.scripted([...])
# and the `fleetwrit_client` pytest fixture
```

Run the bundled examples offline:

```bash
python examples/refund_agent.py
python examples/sre_agent.py
```

## How the fingerprint works

The fingerprint is `sha256:` over the canonical JSON (sorted keys, compact
separators, UTF-8) of `type`, `version`, `tool`, `args`, `agent_id` and
`environment`. The SDK computes it and the server recomputes it. The
idempotency key is `sha256(run_id|step_id|fingerprint)`.

> The v0 canonicaliser is an approximation of RFC 8785 (JCS): it agrees for
> strings, keys, booleans, null and integers, but does not implement JCS
> ECMAScript number formatting for exotic floats. Conformance vectors in
> `protocol/vectors/fingerprint.json` pin the expected bytes for other
> implementations to reproduce.

## Policy engines

```python
from fleetwrit.policy import OPA, Verdict, Policy

guard = fw.guard(policy=OPA(url="http://opa:8181", path="agents/actions/verdict"))
guard.run(issue_refund, charge="ch_123", amount=400000, currency="gbp")
```

A policy returns a `Verdict` of `allow`, `deny` or `ask`. `allow` executes,
`deny` raises `PolicyDenied`, `ask` calls `approve` and then executes the
approved action. OPA and Cedar are stubs in v0; implement `Policy.evaluate`
for a custom engine.

## CLI

```bash
fleetwrit dev            # would start the local server (stub)
fleetwrit actions lint   # lint @action definitions (stub)
fleetwrit ledger verify  # verify the ledger chain (stub)
fleetwrit report         # usage report (stub)
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

`nox` runs the suite across Python 3.10–3.13, the examples, and the
no-framework import check.

## Releasing to PyPI

Publishing is automated by `.github/workflows/publish.yml`, which runs on a
published GitHub Release and uploads via **PyPI Trusted Publishing** (OIDC — no
API token is stored in the repo). One-time setup on PyPI:

1. Register (or reserve) the `fleetwrit` project on PyPI.
2. Add a Trusted Publisher: owner `teopopescu`, repo `fleetwrit-python`,
   workflow `publish.yml`, environment `pypi`.
3. Cut a GitHub Release tagged `v<version>` (matching `pyproject.toml`). The
   workflow builds the sdist + wheel and publishes them.

To publish with an API token instead, add a `PYPI_API_TOKEN` secret and pass it
as `password:` to the publish step.

## Licence

Apache-2.0. Contributions use a DCO sign-off, not a CLA.
