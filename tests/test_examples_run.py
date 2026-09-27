# CALLED BY: pytest -- the examples are real callers of the library, so they cannot rot.
# FIRES WHEN: asked.
"""Every example in `examples/` actually runs.

⛔ AN EXAMPLE IS THE FIRST THING A STRANGER TRIES, so one that has quietly stopped working fails in
front of them instead of in front of us. They are also the clearest statement of what this tool
claims -- an example going red means the claim changed.

⚠ THIS IS NOT DUPLICATE OF `examples/run_all.py`; it is the same runner reached from the test suite,
so the examples are covered whether somebody runs pytest or the workflow. `run_all.py` is what CI
and a human call directly, and it is the ONE definition of which examples exist.
"""
import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_ALL = os.path.join(REPO, "examples", "run_all.py")

sys.path.insert(0, os.path.join(REPO, "examples"))
import run_all as runner                                            # noqa: E402


def test_the_runner_knows_about_every_example_on_disk():
    """The list in run_all.py is the population. An example added to the directory and not to the
    list would never run anywhere -- exactly the built-and-never-called shape this tool looks for."""
    listed = {name for name, _ in runner.EXAMPLES}
    on_disk = {f for f in os.listdir(os.path.join(REPO, "examples"))
               if f.endswith(".py") and not f.startswith("_") and f != "run_all.py"}
    assert on_disk == listed, "examples/ and run_all.EXAMPLES disagree: %s" % (on_disk ^ listed)


@pytest.mark.parametrize("name", [n for n, _ in runner.EXAMPLES])
def test_each_example_runs_clean(name):
    path = os.path.join(REPO, "examples", name)
    r = subprocess.run([sys.executable, path], capture_output=True, text=True)
    assert r.returncode == 0, "%s exited %d:\n%s" % (
        name, r.returncode, (r.stdout + r.stderr)[-1200:])


def test_the_runner_itself_exits_zero():
    r = subprocess.run([sys.executable, RUN_ALL], capture_output=True, text=True)
    assert r.returncode == 0, (r.stdout + r.stderr)[-1500:]
    assert "all %d examples ran clean" % len(runner.EXAMPLES) in r.stdout
