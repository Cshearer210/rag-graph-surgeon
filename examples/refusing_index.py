#!/usr/bin/env python3
"""The trap that looks like the best possible result.

An index that declines every nonsense probe separates PERFECTLY from noise -- an infinite gap, a
flawless score. It is also completely useless if it declines your real questions too, and the
numbers alone cannot tell those apart. So the verdict names the refusal instead of celebrating
the separation.

Run:  python examples/refusing_index.py     ->  exit 0
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))      # the repo root, so a checkout needs no install
sys.path.insert(0, _HERE)                       # so `_fixtures` resolves

from _fixtures import REAL_QUESTIONS                                    # noqa: E402
from ragghost import ranks_meaning                                      # noqa: E402


def query(text):
    if text in REAL_QUESTIONS:
        return 0.80, "docs/extraction-handbook.md"
    return None, None                       # declined: NOT a low score


def main():
    v = ranks_meaning.judge(query, REAL_QUESTIONS, seed=7)
    print(v)
    assert "refused" in v.headline.lower(), (
        "the headline must NAME the refusal, not report a perfect gap: %r" % v.headline)
    assert "gap" not in v.numbers, "a refusal has no gap to report"
    assert v.numbers["nonsense_refused"] == v.numbers["nonsense_asked"]
    print("\nOK -- reported as a refusal. A `None` score is dropped, never read as 0,")
    print("     because an index that did not answer has not scored low.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
