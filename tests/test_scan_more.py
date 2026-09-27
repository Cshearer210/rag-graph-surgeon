# CALLED BY: pytest -- extra coverage for stage 1 (SCAN).
# FIRES WHEN: asked.
"""Error paths, boundaries, and report branches for scan.py that the core suite does not reach."""
import io
import os

import pytest

import importlib
scan = importlib.import_module("ragghost.scan")
from ragghost.scan import Result, VENDORED, _kind, _independent_count


# ── _kind: the classifier, every branch ────────────────────────────────────
@pytest.mark.parametrize("name,expected", [
    ("a.py", "code"), ("A.PY", "code"), ("x.tsx", "code"),
    ("c.json", "config"), ("c.YAML", "config"),
    ("r.md", "docs"), ("r.rst", "docs"),
    ("d.csv", "data"), ("d.jsonl", "data"),
    ("p.png", "media"), ("v.mp4", "media"),
    ("w.html", "web"), ("w.svg", "web"),
    ("noext", "other"), ("weird.qqq", "other"), ("archive.tar.gz", "other"),
])
def test_kind_classifies_by_extension(name, expected):
    assert _kind(name) == expected


def test_kind_is_case_insensitive():
    assert _kind("READ.MD") == _kind("read.md") == "docs"


# ── byte accounting and depth boundaries ────────────────────────────────────
def test_bytes_are_summed(tree):
    d = tree({"a.py": "12345", "b.py": "678"})
    r = scan.scan(d)
    assert r.bytes == 8


def test_depth_zero_at_root(tree):
    d = tree({"top.py": "x"})
    assert scan.scan(d).deepest == 0


def test_by_dir_is_keyed_by_a_forward_slashed_identifier(tree):
    """`by_dir`'s keys are IDENTIFIERS, so they are forward-slashed on every platform.

    ⛔ THIS ASSERTION USED TO READ `r.by_dir[os.path.join("pkg", "sub")]`, AND THAT WAS THE BUG
    WRITTEN INTO THE TEST. `os.path.join` in an EXPECTED value makes the expectation platform-
    dependent: on Linux it is `pkg/sub` and on Windows `pkg\\sub`, so the test agreed with whatever
    the code did on the machine it ran on and could never notice the two disagreeing. Caught only
    when the CI matrix gained Windows (2026-09-27): the fix that normalised the key turned this red
    there and stayed green on Linux and macOS -- which is precisely the value of the matrix.

    A path used to OPEN a file belongs to the platform. A path used as a dict KEY, compared, or
    printed in a report is an identifier, and it is the same string everywhere.
    """
    d = tree({"pkg/mod.py": "x", "pkg/sub/deep.py": "x"})
    r = scan.scan(d)
    assert r.by_dir["pkg"] == 1
    assert r.by_dir["pkg/sub"] == 1
    assert not any("\\" in k for k in r.by_dir), \
        "a by_dir key carried a backslash: %r" % sorted(r.by_dir)


# ── vendored exclusion is honoured and is customisable ──────────────────────
def test_custom_skip_list_overrides_default(tree):
    d = tree({"mine.py": "x", "node_modules/dep.js": "x"})
    # with an empty skip set, node_modules is counted as ordinary content
    r = scan.scan(d, skip=())
    assert r.files == 2
    assert "node_modules" not in r.skipped_dirs


def test_default_skip_is_vendored_constant(tree):
    d = tree({"mine.py": "x"})
    r = scan.scan(d, skip=VENDORED)
    assert r.files == 1


# ── error paths ─────────────────────────────────────────────────────────────
def test_getsize_failure_marks_unreadable_not_absent(tree, monkeypatch):
    d = tree({"a.py": "x", "b.py": "y"})
    real = os.path.getsize

    def flaky(p):
        if p.endswith("b.py"):
            raise OSError("permission denied")
        return real(p)

    monkeypatch.setattr(scan.os.path, "getsize", flaky)
    r = scan.scan(d)
    assert r.files == 1                         # only a.py counted
    assert any("b.py" in u for u in r.unreadable)


def test_independent_count_returns_none_on_scandir_error(tree, monkeypatch):
    d = tree({"a.py": "x"})

    def boom(_p):
        raise OSError("cannot list")

    monkeypatch.setattr(scan.os, "scandir", boom)
    assert _independent_count(d, set()) is None


def test_independent_count_matches_walk_on_healthy_tree(tree):
    d = tree({"a.py": "x", "b/c.py": "x", "b/d.md": "x"})
    assert _independent_count(d, set(VENDORED)) == 3


# ── Result.agrees / exit_code, the three-outcome contract ───────────────────
def test_agrees_is_none_when_second_count_missing():
    r = Result()
    r.files = 3
    r.independent = None
    assert r.agrees is None
    assert r.exit_code() == 2


def test_agrees_true_only_on_equal_counts():
    r = Result()
    r.files = 4
    r.independent = 4
    assert r.agrees is True
    assert r.exit_code() == 0


def test_exit_code_is_two_when_no_files():
    r = Result()
    r.files = 0
    r.independent = 0
    assert r.exit_code() == 2


# ── report output branches ──────────────────────────────────────────────────
def test_report_shows_agreement_line(tree):
    d = tree({"a.py": "x", "b.md": "y"})
    buf = io.StringIO()
    scan.scan(d).report(buf)
    text = buf.getvalue()
    assert "THE DENOMINATOR, COUNTED A SECOND WAY" in text
    assert "They agree." in text


def test_report_flags_disagreement(tree):
    d = tree({"a.py": "x"})
    r = scan.scan(d)
    r.independent = r.files + 3
    buf = io.StringIO()
    r.report(buf)
    assert "THE DISAGREEMENT IS THE FINDING" in buf.getvalue()


def test_report_says_unknown_when_second_count_missing(tree):
    d = tree({"a.py": "x"})
    r = scan.scan(d)
    r.independent = None
    buf = io.StringIO()
    r.report(buf)
    assert "UNKNOWN" in buf.getvalue()


def test_report_names_skipped_dirs(tree):
    d = tree({"mine.py": "x", "node_modules/dep/a.js": "x"})
    buf = io.StringIO()
    scan.scan(d).report(buf)
    assert "DELIBERATELY NOT COUNTED" in buf.getvalue()
    assert "node_modules" in buf.getvalue()


def test_report_on_empty_says_nothing_found():
    r = Result()
    r.root = "/x"
    buf = io.StringIO()
    r.report(buf)
    assert "NOTHING FOUND" in buf.getvalue()


def test_scan_of_a_file_path_is_unknown(tree):
    d = tree({"a.py": "x"})
    r = scan.scan(os.path.join(d, "a.py"))
    assert r.exit_code() == 2
    assert r.unreadable
