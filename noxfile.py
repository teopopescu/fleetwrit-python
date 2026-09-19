"""Nox sessions for the Fleetwrit SDK: tests, examples, import check.

Run ``nox`` for the full matrix, or ``nox -s tests`` for a single session.
"""

from __future__ import annotations

import nox

PYTHONS = ["3.10", "3.11", "3.12", "3.13"]


@nox.session(python=PYTHONS)
def tests(session: nox.Session) -> None:
    """Install the package with dev extras and run the test suite."""
    session.install("-e", ".[dev]")
    session.run("pytest", *session.posargs)


@nox.session(python=PYTHONS[-1])
def examples(session: nox.Session) -> None:
    """Run the offline examples end to end."""
    session.install("-e", ".")
    session.run("python", "examples/refund_agent.py")
    session.run("python", "examples/sre_agent.py")


@nox.session(python=PYTHONS[-1])
def imports(session: nox.Session) -> None:
    """Confirm integrations import with no frameworks installed."""
    session.install("-e", ".")
    session.run(
        "python", "-c", "import fleetwrit; import fleetwrit.integrations.langchain"
    )
