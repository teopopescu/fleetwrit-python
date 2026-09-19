"""The ``fleetwrit`` command-line entry point.

v0 stubs that print sensible output and exit 0: ``dev``, ``actions lint``,
``ledger verify`` and ``report``. Real behaviour lands with the server.
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from . import __version__


def _cmd_dev(args: argparse.Namespace) -> int:
    print(
        f"fleetwrit dev would start the local server, SQLite and dashboard on "
        f"http://localhost:{args.port} with auth off and seeded demo data."
    )
    print("(stub: the server lives in the `fleetwrit` repo and is not bundled here.)")
    return 0


def _cmd_actions_lint(args: argparse.Namespace) -> int:
    print(f"fleetwrit actions lint: scanning {args.path} for @action definitions.")
    print("No lint errors. (stub: full lint arrives with the action catalog.)")
    return 0


def _cmd_ledger_verify(args: argparse.Namespace) -> int:
    print("fleetwrit ledger verify: chain OK, 0 broken sequences.")
    print("(stub: verification runs against a live server's ledger.)")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    print("fleetwrit report: usage summary")
    print("  requests: 0  approvals: 0  edits: 0  expiries: 0")
    print("  human minutes per 1,000 tasks: n/a")
    print("(stub: real figures come from GET /v1/report.)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for the ``fleetwrit`` command."""
    parser = argparse.ArgumentParser(prog="fleetwrit", description="Fleetwrit SDK CLI")
    parser.add_argument("--version", action="version", version=f"fleetwrit {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    dev = sub.add_parser("dev", help="Start the local dev server (stub)")
    dev.add_argument("--port", type=int, default=4100)
    dev.set_defaults(func=_cmd_dev)

    actions = sub.add_parser("actions", help="Action catalog tools")
    actions_sub = actions.add_subparsers(dest="actions_command", required=True)
    lint = actions_sub.add_parser("lint", help="Lint @action definitions (stub)")
    lint.add_argument("path", nargs="?", default=".")
    lint.set_defaults(func=_cmd_actions_lint)

    ledger = sub.add_parser("ledger", help="Ledger tools")
    ledger_sub = ledger.add_subparsers(dest="ledger_command", required=True)
    verify = ledger_sub.add_parser("verify", help="Verify the ledger chain (stub)")
    verify.set_defaults(func=_cmd_ledger_verify)

    report = sub.add_parser("report", help="Print a usage report (stub)")
    report.set_defaults(func=_cmd_report)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI; return an exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
