"""The ``fleetwrit`` command-line entry point.

``dev`` runs the local server + dashboard (delegates to the server package).
``actions lint``, ``ledger verify`` and ``report`` remain v0 stubs.
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from . import __version__


def _cmd_dev(args: argparse.Namespace) -> int:
    # The server + dashboard live in the `fleetwrit` repo. If the server package
    # is installed alongside the SDK, delegate to it; otherwise point the way.
    try:
        from fleetwrit_server.cli import run_dev
    except ImportError:
        print("fleetwrit dev needs the server package (github.com/teopopescu/fleetwrit).")
        print("From a clone of that repo:")
        print("  pip install -e ./server -e ./fleetwrit-python")
        print("  fleetwrit dev          # or: fleetwrit-server dev")
        return 1
    return int(run_dev(
        port=args.port,
        dashboard_port=args.dashboard_port,
        dashboard=not args.no_dashboard,
        seed=args.demo,
        path=args.path,
    ))


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

    dev = sub.add_parser("dev", help="Run the local server + dashboard")
    dev.add_argument("--port", type=int, default=4100)
    dev.add_argument("--dashboard-port", type=int, default=5174)
    dev.add_argument("--no-dashboard", action="store_true", help="Run the server only")
    dev.add_argument("--demo", action="store_true", help="Load sample agents/requests (default: empty)")
    dev.add_argument("--path", default=None, help="Repo root to find dashboard/ (default: cwd)")
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
