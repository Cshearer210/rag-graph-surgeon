# CALLED BY: pytest -- coverage for the self-contained demo.
# FIRES WHEN: asked.
"""The demo builds a tiny broken system in a temp dir, runs every stage live, and cleans up.
These tests assert it returns success, prints the planted findings, and leaves nothing behind."""
import glob
import os
import tempfile

from ragghost.demo import main as demo_main


def test_demo_returns_zero_and_prints_findings(capsys):
    assert demo_main([]) == 0
    out = capsys.readouterr().out
    assert "rag-ghost demo" in out
    # the four planted problems are each surfaced by name
    assert "orphans" in out
    assert "dangling" in out
    assert "misfiled" in out
    assert "ungated subsystems" in out
    assert "ONE PASS" in out or "FAN OUT" in out


def test_demo_reports_the_expected_planted_shapes(capsys):
    demo_main([])
    out = capsys.readouterr().out
    assert "exporter.py" in out          # the orphan
    assert "warehouse" in out            # the moved reference
    assert "test_sync.py" in out         # the misfiled test
    assert "shipping" in out             # the ungated subsystem


def test_demo_cleans_up_its_temp_dir():
    before = set(glob.glob(os.path.join(tempfile.gettempdir(), "ragghost_demo_*")))
    demo_main([])
    after = set(glob.glob(os.path.join(tempfile.gettempdir(), "ragghost_demo_*")))
    assert after <= before, "the demo must remove the temp system it built"
