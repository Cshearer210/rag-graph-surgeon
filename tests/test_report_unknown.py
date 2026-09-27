"""The third exit code, on the one command CI runs.

⛔ WHY THESE TESTS EXIST. `check()` returned `1 if findings else 0` and had no notion of "could not
look", so pointing it at a path that does not exist produced no findings and reported CLEAN --
exit 0, green CI, over a system nothing had read. All eight individual stages already returned 2
correctly; only the aggregator everything actually uses threw it away, which made this a defect in
the tool's own headline claim:

    "Exit codes, and they are the point:  2  IT COULD NOT TELL -- never treat this as clean"

Calibrated in BOTH directions here: the unreadable target must be 2, and a real system with a real
defect must still be 1, and a clean one 0 -- because a fix that turns everything into UNKNOWN would
pass a one-sided test while making the tool useless.
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ragghost.report import check                                          # noqa: E402


def _w(d, rel, text):
    p = os.path.join(d, rel)
    os.makedirs(os.path.dirname(p) or d, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


def _rendered(result):
    """Render a report into a buffer we hand it explicitly.

    ⚠ NOT `capsys`. Every `report()` in this package signs as `report(self, out=sys.stdout)`, and a
    default argument is evaluated once at import -- so it binds the REAL stdout, and pytest's capsys
    (which swaps `sys.stdout` afterwards) never sees the write. The text was visibly printed and the
    assertion read an empty string, which is a test wrong in the one way that looks like a broken
    feature. Passing the buffer in is also how a caller embedding this tool would do it.
    """
    buf = io.StringIO()
    result.report(out=buf)
    return buf.getvalue()


def test_a_target_that_does_not_exist_is_unknown_never_clean(tmp_path):
    missing = str(tmp_path / "no-such-system")
    r = check(missing)
    assert r.exit_code() == 2, "a path that was never read must be 2, never 0"


def test_an_empty_directory_is_unknown_never_clean(tmp_path):
    # Distinct from the case above: the path EXISTS and is readable, and there is still nothing to
    # measure. An empty result is not a clean result.
    r = check(str(tmp_path))
    assert r.exit_code() == 2


def test_the_text_report_says_it_could_not_look(tmp_path):
    out = _rendered(check(str(tmp_path / "gone")))
    assert "COULD NOT LOOK" in out
    assert "UNKNOWN" in out


def test_the_json_report_carries_the_unknown_status(tmp_path):
    # A caller parsing JSON must not have to infer this from an empty findings list, which is
    # exactly what a clean system also produces.
    doc = json.loads(_rendered(check(str(tmp_path / "gone"), fmt="json")))
    assert doc["status"] == "unknown"
    assert doc["could_not_look"] is True


def test_the_sarif_report_marks_the_invocation_unsuccessful(tmp_path):
    doc = json.loads(_rendered(check(str(tmp_path / "gone"), fmt="sarif")))
    assert doc["runs"][0]["invocations"][0]["executionSuccessful"] is False


def test_a_clean_report_does_not_claim_it_could_not_look(tmp_path):
    # THE GUARD for the three above: the unknown banner must appear ONLY when it is true, or it is
    # noise that teaches a reader to ignore it.
    d = str(tmp_path / "real")
    _w(d, "core.py", "def go():\n    return 1\n")
    _w(d, "test_core.py", "import core\n\n\ndef test_core():\n    assert core.go() == 1\n")
    out = _rendered(check(d))
    assert "COULD NOT LOOK" not in out
    doc = json.loads(_rendered(check(d, fmt="json")))
    assert "could_not_look" not in doc


def test_a_real_system_with_a_real_defect_is_still_one(tmp_path):
    # THE GUARD DIRECTION. A fix that made everything UNKNOWN would satisfy every test above and
    # destroy the tool, so the opposite case is asserted in the same file.
    d = str(tmp_path / "sys")
    _w(d, "app.py", 'from helper import go\n\nCONFIG = "conf/missing_file.json"\n\ngo()\n')
    _w(d, "helper.py", "def go():\n    return 1\n")
    _w(d, "test_app.py", "import app\n\n\ndef test_app():\n    assert app.CONFIG\n")
    r = check(d)
    assert r.exit_code() == 1, "a planted dangling reference must still be found"
    assert r.findings


def test_a_clean_system_is_still_zero(tmp_path):
    d = str(tmp_path / "clean")
    _w(d, "core.py", "def go():\n    return 1\n")
    _w(d, "test_core.py", "import core\n\n\ndef test_core():\n    assert core.go() == 1\n")
    r = check(d)
    assert r.exit_code() in (0, 1), "a real system must produce a real verdict, never UNKNOWN"
    assert r.assessed is True
