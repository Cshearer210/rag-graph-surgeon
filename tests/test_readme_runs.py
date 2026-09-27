# CALLED BY: pytest -- the README's claims, reached from the test suite as well as from CI.
# FIRES WHEN: asked.
"""The README still describes this tool.

⛔ THE README IS THE ONE FILE EVERY STRANGER READS AND THE ONE FILE NO TEST TOUCHES, so it rots
silently and fails in front of the person you most wanted to impress. It had already drifted twice in
this repo inside a day — a test count typed at 355 when the real figure was 354, and a coverage
figure at 84% when it was 87% — both written from memory, in a document whose own subject is that a
description of a system is evidence about the past.

The heavy half (running every documented command) lives in `tools/readme_runs.py` so CI and a human
call the same thing. What is here is the cheap half plus the link check, so `pytest` alone catches a
dead link or a number nobody can verify.
"""
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
import readme_runs                                                  # noqa: E402


def test_every_relative_link_in_the_readme_exists():
    """A dead link in the front door is the GRAPH-DANGLING class this tool advertises, sitting in
    the file a stranger reads first."""
    assert readme_runs.check_links() == []


def test_the_readme_states_numbers_this_can_verify():
    """Not whether they are RIGHT — that needs a run, and CI does it. This asserts they are still
    stated in a form something can check, because a number nobody can re-derive is a number that
    goes stale in silence."""
    assert readme_runs.check_numbers(recount=False) == []


def test_the_documented_stage_exit_codes_hold():
    """`scan` clean, `graph` and `plan` finding a planted orphan — against a system built here, so
    the expected codes are not hostage to this repository's own state."""
    assert readme_runs.check_synthetic_stages() == []


def test_the_runner_itself_is_runnable_and_reports_a_verdict():
    """The cheap path only: the full command sweep runs its own subprocesses and belongs in CI."""
    r = subprocess.run([sys.executable, os.path.join(REPO, "tools", "readme_runs.py"), "--help"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "README" in r.stdout
