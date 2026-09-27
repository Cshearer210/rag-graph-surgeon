#!/usr/bin/env python3
"""The one most graders pass: every score identical, so the gap is exactly 0.0.

"Not worse than nonsense" is not "better than nonsense". A `>=` where a `>` belongs turns an index
that can separate nothing from anything into a clean bill of health.

Run:  python examples/flat_index.py     ->  exit 0
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))      # the repo root, so a checkout needs no install
sys.path.insert(0, _HERE)                       # so `_fixtures` resolves

from _fixtures import REAL_QUESTIONS                                    # noqa: E402
from ragghost import ranks_meaning                                      # noqa: E402


def query(_text):
    return 0.5, "docs/everything.md"


def main():
    v = ranks_meaning.judge(query, REAL_QUESTIONS, seed=7)
    print(v)
    assert v.code == 1, "a dead heat is not a pass, got %d" % v.code
    assert v.numbers["gap"] == 0.0
    print("\nOK -- a tie is reported as a problem, not as 'no worse than noise'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
