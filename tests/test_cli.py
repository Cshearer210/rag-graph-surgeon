# CALLED BY: pytest -- coverage for the command line (__main__.main).
# FIRES WHEN: asked.
"""Every command, every exit path, and the three-outcome exit-code contract of the CLI.

The stage report() methods bind sys.stdout as a default argument at import time, so their printed
output does not surface through pytest's capsys/capfd (it lands in pytest's own global capture).
The CLI's real, documented contract is its EXIT CODE and, for `fix`, its effect on disk -- those
are what these tests assert. The exact report TEXT is proven separately in the per-stage report
tests, which pass an explicit buffer. Usage/help/error text is printed via sys.stdout.write at call
time, so those ARE capturable and are checked here.
"""
import os

import pytest

from ragghost.__main__ import main


BROKEN = {
    "reports/__init__.py": "", "reports/exporter.py": "def e(): return 1\n",
    "inventory/__init__.py": "", "inventory/sync.py": "from inventory import warehouse\n",
    "inventory/test_sync.py": "def test(): assert True\n",
    "shipping/__init__.py": "", "shipping/labels.py": "def m(): return 'L'\n",
    "tests/test_reports.py": "from reports import exporter\n",
}

CLEAN = {
    "pkg/__init__.py": "", "pkg/core.py": "def c(): return 1\n",
    "pkg/__main__.py": "from pkg import core\n",
    "tests/test_core.py": "from pkg import core\ndef test(): assert core.c()\n",
}


# ── usage / help (written via sys.stdout.write at call time -> capturable) ───
def test_no_args_prints_usage_and_exits_zero(capsys):
    assert main([]) == 0
    assert "rag-ghost" in capsys.readouterr().out


@pytest.mark.parametrize("flag", ["-h", "--help", "help"])
def test_help_flags(flag, capsys):
    assert main([flag]) == 0
    assert "Exit codes" in capsys.readouterr().out


def test_unknown_command_is_could_not_tell(capsys):
    assert main(["frobnicate", "/tmp"]) == 2
    assert "unknown command" in capsys.readouterr().out


def test_stage_without_a_path_is_could_not_tell(capsys):
    assert main(["scan"]) == 2
    assert "needs a path" in capsys.readouterr().out


def test_check_without_a_path_is_could_not_tell(capsys):
    assert main(["check"]) == 2
    assert "needs a path" in capsys.readouterr().out


# ── each stage over a broken tree returns "found something" (1) ─────────────
@pytest.mark.parametrize("cmd", ["graph", "organize", "harness", "plan"])
def test_stage_finds_something_in_broken_tree(cmd, tree):
    d = tree(BROKEN)
    assert main([cmd, d]) == 1


def test_scan_of_broken_tree_scans_clean(tree):
    # scan itself only fails when the two file counts disagree; a readable tree scans to 0
    d = tree(BROKEN)
    assert main(["scan", d]) == 0


# ── each stage over a clean tree returns clean (0) ──────────────────────────
@pytest.mark.parametrize("cmd", ["scan", "graph", "organize", "harness", "plan"])
def test_stage_clean_tree_exits_zero(cmd, tree):
    d = tree(CLEAN)
    assert main([cmd, d]) == 0


# ── analyse returns a decision, never UNKNOWN, on a real tree ───────────────
def test_analyse_returns_a_decision(tree):
    d = tree(CLEAN)
    assert main(["analyse", d]) in (0, 1)


def test_analyse_empty_tree_is_could_not_tell(tmp_path):
    assert main(["analyse", str(tmp_path)]) == 2


# ── check: exit-code contract across formats and config ─────────────────────
def test_check_broken_tree_finds_something(tree):
    d = tree(BROKEN)
    assert main(["check", d]) == 1


def test_check_json_format_runs(tree):
    d = tree(BROKEN)
    assert main(["check", d, "--format", "json"]) == 1


def test_check_sarif_format_equals_syntax_runs(tree):
    d = tree(BROKEN)
    assert main(["check", d, "--format=sarif"]) == 1


def test_check_clean_tree_exits_zero(tree):
    d = tree(CLEAN)
    assert main(["check", d]) == 0


# ── fix: dry run leaves disk untouched, --apply moves the file ──────────────
def test_fix_dry_run_does_not_move(tree):
    d = tree(BROKEN)
    main(["fix", d])
    assert os.path.exists(os.path.join(d, "inventory/test_sync.py"))
    assert not os.path.exists(os.path.join(d, "tests/test_sync.py"))


def test_fix_apply_moves_the_file(tree):
    d = tree(BROKEN)
    main(["fix", d, "--apply"])
    assert not os.path.exists(os.path.join(d, "inventory/test_sync.py"))
    assert os.path.exists(os.path.join(d, "tests/test_sync.py"))


# ── demo runs from the CLI (demo reads sys.stdout at call time -> capturable) ─
def test_demo_command_runs(capsys):
    assert main(["demo"]) == 0
    assert "rag-ghost demo" in capsys.readouterr().out
