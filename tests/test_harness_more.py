# CALLED BY: pytest -- extra coverage for stage 5 (HARNESS).
# FIRES WHEN: asked.
"""Component grouping, the gate rule, and every report branch of harness.py."""
import io

import pytest

from ragghost.harness import harnesses, Harnesses, _component


# ── _component: the grouping key ────────────────────────────────────────────
@pytest.mark.parametrize("path,expected", [
    ("billing/charge.py", "billing"),
    ("billing/sub/deep.py", "billing"),
    ("toplevel.py", "(root)"),
    ("tests/test_x.py", "tests"),
])
def test_component(path, expected):
    assert _component(path) == expected


# ── the gate rule ───────────────────────────────────────────────────────────
def test_harness_with_own_tests_is_gated(tree):
    d = tree({
        "billing/__init__.py": "", "billing/charge.py": "def c(): return 1\n",
        "billing/tests/test_charge.py": "def test(): assert True\n",
    })
    h = harnesses(d)
    assert "billing" not in h.ungated


def test_harness_imported_by_a_test_is_gated(tree):
    d = tree({
        "billing/__init__.py": "", "billing/charge.py": "def c(): return 1\n",
        "tests/test_billing.py": "from billing import charge\ndef test(): assert charge.c()\n",
    })
    h = harnesses(d)
    assert "billing" not in h.ungated


def test_code_harness_with_no_test_is_ungated(tree):
    d = tree({
        "shipping/__init__.py": "", "shipping/labels.py": "def m(): return 'L'\n",
        "tests/test_other.py": "def test(): assert True\n",
    })
    h = harnesses(d)
    assert "shipping" in h.ungated


def test_ungated_list_is_sorted(tree):
    d = tree({
        "zeta/__init__.py": "", "zeta/z.py": "def z(): return 1\n",
        "alpha/__init__.py": "", "alpha/a.py": "def a(): return 1\n",
        "tests/test_none.py": "def test(): assert True\n",
    })
    h = harnesses(d)
    assert h.ungated == sorted(h.ungated)
    assert "alpha" in h.ungated and "zeta" in h.ungated


# ── doors: the cross-harness public surface ─────────────────────────────────
def test_doors_are_files_reached_from_another_harness(tree):
    d = tree({
        "api/__init__.py": "", "api/handler.py": "from core import engine\n",
        "core/__init__.py": "", "core/engine.py": "def run(): return 1\n",
        "tests/test_all.py": "from api import handler\nfrom core import engine\n",
    })
    h = harnesses(d)
    assert "core/engine.py" in h.groups["core"]["doors"]


# ── exit codes ──────────────────────────────────────────────────────────────
def test_empty_is_unknown():
    assert Harnesses().exit_code() == 2


def test_ungated_found_something():
    h = Harnesses()
    h.groups = {"x": {"files": {"x/a.py"}, "code": {"x/a.py"}, "doors": set(),
                      "gated": False, "tests": set()}}
    h.ungated = ["x"]
    assert h.exit_code() == 1


def test_all_gated_is_clean():
    h = Harnesses()
    h.groups = {"x": {"files": {"x/a.py"}, "code": {"x/a.py"}, "doors": set(),
                      "gated": True, "tests": {"x/test_a.py"}}}
    assert h.exit_code() == 0


# ── report() branches ───────────────────────────────────────────────────────
def test_report_lists_each_harness_with_its_gate(tree):
    d = tree({
        "shipping/__init__.py": "", "shipping/labels.py": "def m(): return 'L'\n",
        "tests/test_other.py": "def test(): assert True\n",
    })
    buf = io.StringIO()
    harnesses(d).report(buf)
    text = buf.getvalue()
    assert "EACH HARNESS" in text
    assert "WITH NO GATE" in text


def test_report_clean_message(tree):
    d = tree({
        "billing/__init__.py": "", "billing/charge.py": "def c(): return 1\n",
        "tests/test_billing.py": "from billing import charge\ndef test(): assert charge.c()\n",
    })
    buf = io.StringIO()
    harnesses(d).report(buf)
    assert "Every code harness has a gate." in buf.getvalue()


def test_report_empty_is_unknown():
    h = Harnesses()
    h.root = "/x"
    buf = io.StringIO()
    h.report(buf)
    assert "NO HARNESSES" in buf.getvalue()
