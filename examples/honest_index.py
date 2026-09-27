#!/usr/bin/env python3
"""An index that works: real questions score high, generated nonsense scores low.

Run:  python examples/honest_index.py     ->  exit 0
"""
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))      # the repo root, so a checkout needs no install
sys.path.insert(0, _HERE)                       # so `_fixtures` resolves

from _fixtures import REAL_QUESTIONS                                    # noqa: E402
from ragghost import ranks_meaning                                      # noqa: E402


def query(text):
    """The one function the tool ever needs: text -> (score, path)."""
    known = text in REAL_QUESTIONS
    jitter = random.Random(text).random() * 0.10
    if known:
        return 0.82 + jitter, "docs/extraction-handbook.md"
    return 0.11 + jitter, "docs/unrelated.md"


def main():
    v = ranks_meaning.judge(query, REAL_QUESTIONS, seed=7)
    print(v)
    assert v.code == 0, "an index this clean must come back 0, got %d" % v.code
    assert v.numbers["gap"] > 0.5, "the gap should be wide here"
    print("\nOK -- the tool agrees this index ranks meaning above noise.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
