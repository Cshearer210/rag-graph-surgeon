"""The before/after demo is a real caller of the surgeon, so it cannot rot: this test runs it and
asserts the story it tells is true — the broken shop gets fixes applied, judgement calls surfaced,
and a storefront actually shipped."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "examples"))
import before_after_demo as demo  # noqa: E402


def test_demo_runs_and_ships():
    code, proof, out = demo._run_surgeon()
    assert code == 0, "the surgeon should exit 0 (shipped and graded clean)"
    assert proof is not None, "the demo must get a readable proof back"
    # BEFORE was genuinely broken: at least the three auto-fixable defects were found and fixed.
    assert len(proof.get("fixed", [])) >= 3, "the three planted fixable defects should be fixed"
    # AFTER: real judgement calls were handed back, not guessed at.
    assert len(proof.get("surfaced_for_owner", [])) >= 1, "unsafe fixes must be surfaced, not applied"
    # SHIPPED: a working storefront exists on disk.
    assert proof.get("shipped"), "a storefront should have shipped"
    assert os.path.exists(os.path.join(out, "index.html")), "the shipped store needs an index page"


def test_demo_run_returns_success():
    assert demo.run(show_open=False) == 0
