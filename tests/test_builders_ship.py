"""Every declared-built output type must actually ship its output on a real (broken) system.
This is the guard behind the claim 'ships a wide variety of software and outputs' -- if a builder
regresses, one of these fails instead of the demo quietly shrinking."""
import os
import subprocess
import sys
import tempfile

import pytest

REPO = os.path.join(os.path.dirname(__file__), "..")
BROKEN = os.path.join(REPO, "examples", "broken-shop")

# output type -> a file that MUST exist in the shipped output for it to count as shipped
EXPECT = {
    "landing": "index.html",
    "dashboard": "index.html",
    "api": os.path.join("api", "index.json"),
    "cli": "tool.py",
}


@pytest.mark.parametrize("output,expect", sorted(EXPECT.items()))
def test_builder_ships(output, expect):
    ws = tempfile.mkdtemp()
    out = tempfile.mkdtemp()
    r = subprocess.run(
        [sys.executable, "-m", "ragghost.surgeon", BROKEN, "--output", output,
         "--name", "Test Co", "--out", out, "--workspace", ws],
        cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, "%s did not ship cleanly:\n%s" % (output, r.stdout[-500:] + r.stderr[-300:])
    assert os.path.exists(os.path.join(out, expect)), "%s shipped without %s" % (output, expect)


def test_cli_tool_actually_runs():
    ws = tempfile.mkdtemp()
    out = tempfile.mkdtemp()
    subprocess.run([sys.executable, "-m", "ragghost.surgeon", BROKEN, "--output", "cli",
                    "--name", "Test Co", "--out", out, "--workspace", ws],
                   cwd=REPO, capture_output=True, text=True)
    tool = os.path.join(out, "tool.py")
    c = subprocess.run([sys.executable, tool, "count"], cwd=out, capture_output=True, text=True)
    assert c.returncode == 0 and c.stdout.strip().isdigit(), "generated cli did not run: %s" % c.stderr
