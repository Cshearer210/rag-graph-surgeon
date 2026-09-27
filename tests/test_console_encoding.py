# CALLED BY: pytest -- the console-encoding guard.
# FIRES WHEN: asked, on every platform, because it BUILDS the hostile console rather than needing one.
"""A report must not crash on a console that cannot encode the characters in it.

⛔ THE DEFECT: every stage marks a finding with `⛔` and a caveat with `⚠`. A Windows console runs
the cp1252 code page, which has neither, so `sys.stdout.write` raised `UnicodeEncodeError` and the
tool printed a traceback instead of its answer — on Windows, for any report that found something.

⚠ AND THE REASON NO TEST SAW IT IS THE POINT OF THIS FILE: pytest captures output into a buffer with
no code page, so **running the tests removed the condition being tested.** A Windows CI job was green
throughout. The only Windows step that wrote to a real console was `ragghost check .`, marked
`continue-on-error` because `check` legitimately exits 1 when it finds something — so a crash and a
finding produced the same green tick.

So this file does not ask the platform for a hostile console. It CONSTRUCTS one, which means it is
the same test on Linux, macOS and Windows, and it cannot be quietly neutralised by the test runner.
Both directions: the first test proves the hazard is real by letting it fire, the rest prove the fix
silences it without swallowing the report.
"""
import io

import pytest

import ragghost
from ragghost.graph import build_graph


def _cp1252_console(errors="strict"):
    """A text stream that behaves like a Windows console: cp1252, and strict by default."""
    return io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors=errors, newline="")


def _a_system_with_a_finding(tree):
    """A tree whose graph report is guaranteed to print the ⛔ marker, because it has an orphan."""
    return tree({
        "main.py": "VALUE = 1\n",
        "orphan.py": "OTHER = 2\n",
    })


def test_the_hazard_is_real_an_unprepared_cp1252_console_raises(tree):
    """MUST-FIRE. If this ever stops raising, the guard below has stopped proving anything."""
    g = build_graph(_a_system_with_a_finding(tree))
    assert g.orphans, "the fixture must produce a finding, or the ⛔ marker is never printed"
    with pytest.raises(UnicodeEncodeError):
        g.report(out=_cp1252_console())


def test_console_safe_makes_the_same_report_print(tree):
    """THE FIX. Same report, same hostile stream, no exception."""
    g = build_graph(_a_system_with_a_finding(tree))
    console = _cp1252_console()
    ragghost.console_safe(console)
    g.report(out=console)                    # must not raise
    console.flush()
    written = console.buffer.getvalue()
    assert written, "the report must still be written, not merely not-crash"


def test_the_report_is_still_readable_afterwards(tree):
    """A fix that silences the crash by swallowing the content would pass the test above."""
    root = _a_system_with_a_finding(tree)
    console = _cp1252_console()
    ragghost.console_safe(console)
    build_graph(root).report(out=console)
    console.flush()
    text = console.buffer.getvalue().decode("utf-8", errors="replace")
    assert "GRAPH" in text
    assert "orphan.py" in text, "the finding itself must survive the encoding fix"


def test_console_safe_is_harmless_on_a_stream_it_cannot_reconfigure():
    """It is called unconditionally by both command lines, so it must never be the thing that
    breaks a run. A plain StringIO has no reconfigure() at all."""
    s = io.StringIO()
    ragghost.console_safe(s)               # must not raise
    s.write("⛔ still works\n")
    assert "⛔" in s.getvalue()


def test_console_safe_returns_what_it_touched():
    """Called with no arguments it prepares the process's own streams; the return value is what makes
    that checkable from a test without reaching into the module."""
    s1, s2 = io.StringIO(), io.StringIO()
    assert ragghost.console_safe(s1, s2) == (s1, s2)


def test_every_stage_report_survives_the_hostile_console(tree):
    """The markers are not unique to stage 2. One sweep over every stage that has a report, so a new
    marker in any of them cannot reintroduce this."""
    root = tree({
        "main.py": "VALUE = 1\n",
        "orphan.py": "OTHER = 2\n",
        "config.json": '{"a": 1}\n',
    })
    for name, fn in (("scan", ragghost.scan), ("graph", build_graph),
                     ("organize", ragghost.organize), ("retrieve", ragghost.build_index),
                     ("harness", ragghost.harnesses), ("plan", ragghost.plan),
                     ("analyse", ragghost.analyse), ("fix", ragghost.fix)):
        console = _cp1252_console()
        ragghost.console_safe(console)
        fn(root).report(out=console)        # must not raise, for any stage
        console.flush()
        assert console.buffer.getvalue(), "%s printed nothing" % name
