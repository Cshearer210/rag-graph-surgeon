# CALLED BY: pytest -- extra coverage for stage 6 (PLAN).
# FIRES WHEN: asked.
"""Harm ranking, the item vocabulary, and every report branch of plan.py."""
import io


from ragghost.plan import plan, Plan, SEV


# ── harm ranking ────────────────────────────────────────────────────────────
def test_items_are_sorted_worst_first(tree):
    d = tree({
        "inventory/__init__.py": "",
        "inventory/sync.py": "from inventory import warehouse\n",   # CRITICAL moved-ref
        "inventory/test_sync.py": "def test(): assert True\n",       # LOW misfiled
        "reports/__init__.py": "",
        "reports/exporter.py": "def e(): return 1\n",               # MEDIUM orphan
        "shipping/__init__.py": "",
        "shipping/labels.py": "def m(): return 'L'\n",              # HIGH no-gate
        "tests/test_reports.py": "from reports import exporter\n",
    })
    items = plan(d).items
    sevs = [SEV[sev] for sev, _, _, _ in items]
    assert sevs == sorted(sevs), "items must be ranked by harm, worst first"


def test_plan_covers_every_finding_kind(tree):
    d = tree({
        "inventory/__init__.py": "",
        "inventory/sync.py": "from inventory import warehouse\n",
        "inventory/test_sync.py": "def test(): assert True\n",
        "reports/__init__.py": "",
        "reports/exporter.py": "def e(): return 1\n",
        "shipping/__init__.py": "",
        "shipping/labels.py": "def m(): return 'L'\n",
    })
    kinds = {k for _, k, _, _ in plan(d).items}
    assert {"moved-ref", "orphan", "no-gate", "misfiled"} <= kinds


def test_severity_map_orders_critical_first():
    assert SEV["CRITICAL"] < SEV["HIGH"] < SEV["MEDIUM"] < SEV["LOW"]


# ── exit codes ──────────────────────────────────────────────────────────────
def test_unassessed_is_unknown():
    p = Plan()
    assert p.assessed is False
    assert p.exit_code() == 2


def test_empty_tree_is_unassessed(tree, tmp_path):
    p = plan(str(tmp_path))
    assert p.assessed is False
    assert p.exit_code() == 2


def test_clean_tree_has_no_items_and_exits_zero(tree):
    d = tree({
        "pkg/__init__.py": "", "pkg/core.py": "def c(): return 1\n",
        "tests/test_core.py": "from pkg import core\ndef test(): assert core.c()\n",
        "pkg/__main__.py": "from pkg import core\n",
    })
    p = plan(d)
    assert p.assessed is True
    assert p.items == []
    assert p.exit_code() == 0


# ── report() branches ───────────────────────────────────────────────────────
def test_report_lists_ranked_actions(tree):
    d = tree({
        "reports/__init__.py": "", "reports/exporter.py": "def e(): return 1\n",
        "tests/test_x.py": "def test(): assert True\n",
    })
    buf = io.StringIO()
    plan(d).report(buf)
    assert "ranked by harm" in buf.getvalue()


def test_report_clean_says_nothing_to_do(tree):
    d = tree({
        "pkg/__init__.py": "", "pkg/core.py": "def c(): return 1\n",
        "tests/test_core.py": "from pkg import core\ndef test(): assert core.c()\n",
        "pkg/__main__.py": "from pkg import core\n",
    })
    buf = io.StringIO()
    plan(d).report(buf)
    assert "Nothing to do." in buf.getvalue()


def test_report_unassessed_is_unknown():
    p = Plan()
    p.root = "/x"
    buf = io.StringIO()
    p.report(buf)
    assert "COULD NOT ASSESS" in buf.getvalue()
