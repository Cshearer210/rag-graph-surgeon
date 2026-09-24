# CALLED BY: pytest -- extra coverage for stage 8 (FIX).
# FIRES WHEN: asked.
"""The one stage that writes: dry-run safety, the prove-and-rollback loop, refusals, and reports."""
import io
import os


import importlib
fix_mod = importlib.import_module("ragghost.fix")
from ragghost.fix import fix, Fixes, Fix, _still_misfiled


BROKEN = {
    "inventory/__init__.py": "",
    "inventory/sync.py": "from inventory import warehouse\n",   # orphan-ish + moved-ref source
    "inventory/test_sync.py": "def test(): assert True\n",       # the misfiled test
    "reports/__init__.py": "",
    "reports/exporter.py": "def e(): return 1\n",               # orphan (refused)
    "shipping/__init__.py": "",
    "shipping/labels.py": "def m(): return 'L'\n",              # no-gate (refused)
    "tests/test_reports.py": "from reports import exporter\n",
}


# ── dry run writes nothing ──────────────────────────────────────────────────
def test_dry_run_does_not_move_the_file(tree):
    d = tree(BROKEN)
    f = fix(d, apply=False)
    assert os.path.exists(os.path.join(d, "inventory/test_sync.py"))
    assert not os.path.exists(os.path.join(d, "tests/test_sync.py"))
    assert f.applied_mode is False
    assert any(x.mechanical and x.proven is None for x in f.fixes)


# ── apply moves the file and proves the fix by re-asking the world ───────────
def test_apply_moves_and_proves(tree):
    d = tree(BROKEN)
    f = fix(d, apply=True)
    assert not os.path.exists(os.path.join(d, "inventory/test_sync.py"))
    assert os.path.exists(os.path.join(d, "tests/test_sync.py"))
    mech = [x for x in f.fixes if x.mechanical]
    assert mech and all(x.proven is True for x in mech)


# ── the rollback loop: if the proof does not flip, the edit is reverted ──────
def test_apply_rolls_back_when_proof_does_not_flip(tree, monkeypatch):
    d = tree(BROKEN)
    # force the re-measurement to claim the file is STILL misfiled -> the fix must roll back
    monkeypatch.setattr(fix_mod, "_still_misfiled", lambda root, rel: True)
    f = fix(d, apply=True)
    # the file is back where it started, and the fix is marked failed
    assert os.path.exists(os.path.join(d, "inventory/test_sync.py"))
    assert not os.path.exists(os.path.join(d, "tests/test_sync.py"))
    mech = [x for x in f.fixes if x.mechanical]
    assert mech and all(x.proven is False for x in mech)
    assert f.exit_code() == 1


# ── refusals: an orphan is never deleted, only reported with its proving check
def test_orphan_is_refused_with_a_named_proof(tree):
    d = tree(BROKEN)
    f = fix(d, apply=False)
    orphan = [x for x in f.fixes if x.kind == "orphan"]
    assert orphan
    assert all(not x.mechanical for x in orphan)
    assert all("graph()" in x.proof for x in orphan)
    # nothing was deleted
    assert os.path.exists(os.path.join(d, "reports/exporter.py"))


def test_destination_clash_is_not_mechanical(tree):
    d = tree({
        "inventory/test_sync.py": "def test(): assert True\n",
        "tests/test_sync.py": "def test(): assert True\n",   # a file already sits at the destination
        "app.py": "X=1\n",
    })
    f = fix(d, apply=False)
    clash = [x for x in f.fixes if x.kind == "misfiled"]
    assert clash and all(not x.mechanical for x in clash)


def test_still_misfiled_helper_reflects_reality(tree):
    d = tree({"src/test_stray.py": "def test(): assert True\n", "src/app.py": "X=1\n"})
    assert _still_misfiled(d, "src/test_stray.py") is True
    assert _still_misfiled(d, "src/app.py") is False


# ── exit codes ──────────────────────────────────────────────────────────────
def test_empty_is_unknown(tree, tmp_path):
    f = fix(str(tmp_path))
    assert f.assessed is False
    assert f.exit_code() == 2


def test_clean_system_has_nothing_to_fix(tree):
    d = tree({
        "pkg/__init__.py": "", "pkg/core.py": "def c(): return 1\n",
        "tests/test_core.py": "from pkg import core\ndef test(): assert core.c()\n",
        "pkg/__main__.py": "from pkg import core\n",
    })
    f = fix(d, apply=False)
    assert f.fixes == []
    assert f.exit_code() == 0


def test_fixes_present_exit_one(tree):
    d = tree(BROKEN)
    assert fix(d, apply=False).exit_code() == 1


# ── the Fix record ──────────────────────────────────────────────────────────
def test_fix_record_defaults():
    item = Fix("orphan", "x/y.py", False, "wire it in")
    assert item.applied is False
    assert item.proven is None
    assert item.proof == ""


# ── report() branches ───────────────────────────────────────────────────────
def test_report_dry_run_says_rerun_with_apply(tree):
    d = tree(BROKEN)
    buf = io.StringIO()
    fix(d, apply=False).report(buf)
    text = buf.getvalue()
    assert "[dry run]" in text
    assert "Re-run with --apply" in text
    assert "NEEDS A HUMAN" in text


def test_report_apply_shows_proof(tree):
    d = tree(BROKEN)
    buf = io.StringIO()
    fix(d, apply=True).report(buf)
    text = buf.getvalue()
    assert "[--apply]" in text
    assert "proof:" in text


def test_report_empty_is_unknown():
    f = Fixes()
    f.root = "/x"
    buf = io.StringIO()
    f.report(buf)
    assert "NOTHING TO FIX" in buf.getvalue()


def test_report_clean_says_nothing_to_fix(tree):
    d = tree({
        "pkg/__init__.py": "", "pkg/core.py": "def c(): return 1\n",
        "tests/test_core.py": "from pkg import core\ndef test(): assert core.c()\n",
        "pkg/__main__.py": "from pkg import core\n",
    })
    buf = io.StringIO()
    fix(d, apply=False).report(buf)
    assert "Nothing to fix." in buf.getvalue()
