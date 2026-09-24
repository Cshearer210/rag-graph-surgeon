# CALLED BY: pytest -- extra coverage for stage 3 (ORGANIZE).
# FIRES WHEN: asked.
"""The tier classifier, pinned/movable split, and every report branch of organize.py."""
import io

import pytest

from ragghost.organize import organize, Index, _tier, _kind_of


# ── _tier: the classifier, every branch ─────────────────────────────────────
@pytest.mark.parametrize("path,is_imported,expected", [
    ("__main__.py", False, "entry"),
    ("cli.py", False, "entry"),
    ("setup.py", False, "entry"),
    ("main.py", False, "entry"),
    ("tests/test_x.py", False, "test"),
    ("pkg/test_thing.py", False, "test"),
    ("pkg/core.py", True, "core"),        # code that something imports
    ("pkg/leaf.py", False, "leaf"),       # code nothing imports
    ("config.json", False, "config"),
    ("readme.md", False, "docs"),
    ("data.csv", False, "data"),
    ("page.html", False, "web"),
    ("logo.png", False, "media"),
    ("mystery.qqq", False, "other"),
])
def test_tier_classifies(path, is_imported, expected):
    assert _tier(path, is_imported) == expected


def test_kind_of_maps_extensions():
    assert _kind_of(".py") == "code"
    assert _kind_of(".json") == "config"
    assert _kind_of(".zzz") == "other"


# ── pinned vs movable ───────────────────────────────────────────────────────
def test_imported_file_is_pinned(tree):
    d = tree({"pkg/__init__.py": "", "pkg/core.py": "X=1\n",
              "pkg/user.py": "from pkg import core\n"})
    idx = organize(d)
    assert "pkg/core.py" in idx.pinned
    assert idx.pinned["pkg/core.py"]           # carries its dependents


def test_unreferenced_file_is_movable(tree):
    d = tree({"pkg/__init__.py": "", "pkg/lonely.py": "X=1\n",
              "pkg/__main__.py": "print('go')\n"})
    idx = organize(d)
    assert "pkg/lonely.py" in idx.movable


def test_total_equals_node_count(tree):
    d = tree({"a.py": "X=1\n", "b.md": "hi", "c.json": "{}"})
    idx = organize(d)
    assert idx.total == 3


# ── misfiled detection ──────────────────────────────────────────────────────
def test_test_file_in_tests_dir_is_not_misfiled(tree):
    d = tree({"tests/test_ok.py": "def test(): assert True\n", "app.py": "X=1\n"})
    assert organize(d).misfiled == []


def test_test_file_outside_tests_dir_is_misfiled(tree):
    d = tree({"src/test_stray.py": "def test(): assert True\n", "src/app.py": "X=1\n"})
    misfiled = [f for f, _ in organize(d).misfiled]
    assert "src/test_stray.py" in misfiled


# ── exit codes ──────────────────────────────────────────────────────────────
def test_empty_index_is_unknown():
    idx = Index()
    idx.total = 0
    assert idx.exit_code() == 2


def test_misfiled_index_found_something():
    idx = Index()
    idx.total = 5
    idx.misfiled = [("x/test_a.py", "why")]
    assert idx.exit_code() == 1


def test_clean_index_is_zero():
    idx = Index()
    idx.total = 5
    assert idx.exit_code() == 0


# ── report() branches ───────────────────────────────────────────────────────
def test_report_shows_tiers_and_load_bearing(tree):
    d = tree({"pkg/__init__.py": "", "pkg/core.py": "X=1\n",
              "pkg/user.py": "from pkg import core\n", "readme.md": "hi"})
    buf = io.StringIO()
    organize(d).report(buf)
    text = buf.getvalue()
    assert "TIERED VIEW" in text
    assert "LOAD-BEARING" in text
    assert "SAFE TO REORGANISE" in text


def test_report_flags_misfiled(tree):
    d = tree({"src/test_stray.py": "def test(): assert True\n", "src/app.py": "X=1\n"})
    buf = io.StringIO()
    organize(d).report(buf)
    assert "CLEARLY MISFILED" in buf.getvalue()


def test_report_clean_says_nothing_misfiled(tree):
    d = tree({"tests/test_ok.py": "def test(): assert True\n", "app.py": "X=1\n"})
    buf = io.StringIO()
    organize(d).report(buf)
    assert "No file is clearly misfiled." in buf.getvalue()


def test_report_on_empty_is_unknown():
    idx = Index()
    idx.root = "/x"
    buf = io.StringIO()
    idx.report(buf)
    assert "NOTHING TO INDEX" in buf.getvalue()
