"""The ``fleetwrit`` CLI: stub subcommands, the dev guidance path, and --version."""

from __future__ import annotations

import pytest

from fleetwrit.cli import build_parser, main


def test_actions_lint_returns_zero() -> None:
    assert main(["actions", "lint"]) == 0


def test_ledger_verify_returns_zero() -> None:
    assert main(["ledger", "verify"]) == 0


def test_report_returns_zero() -> None:
    assert main(["report"]) == 0


def test_dev_without_server_points_the_way(capsys: pytest.CaptureFixture[str]) -> None:
    # fleetwrit_server is not installed in this env, so the ImportError path runs.
    assert main(["dev"]) == 1
    out = capsys.readouterr().out
    assert "dev-server" in out


def test_build_parser_builds() -> None:
    build_parser()


def test_version_exits_zero() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
