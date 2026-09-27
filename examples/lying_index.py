#!/usr/bin/env python3
"""The failure this whole project exists for, reproduced exactly.

These two numbers are not invented. In a real, live embedding index with 82,000+ chunks, random
hexadecimal scored 0.735 while real questions scored 0.687. Nonsense outranked meaning, every
answer built on it came back confident, and nothing anywhere raised an error.

Run:  python examples/lying_index.py     ->  exit 0 (the TOOL was right; the INDEX was not)
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))      # the repo root, so a checkout needs no install
sys.path.insert(0, _HERE)                       # so `_fixtures` resolves

from _fixtures import REAL_QUESTIONS                                    # noqa: E402
from ragghost import ranks_meaning                                      # noqa: E402

REAL_SCORE, NOISE_SCORE = 0.687, 0.735          # measured, not chosen


def query(text):
    if text in REAL_QUESTIONS:
        return REAL_SCORE, "docs/extraction-handbook.md"
    return NOISE_SCORE, "docs/extraction-handbook.md"


def main():
    v = ranks_meaning.judge(query, REAL_QUESTIONS, seed=7)
    print(v)
    assert v.code == 1, "nonsense above meaning must be a FINDING, got %d" % v.code
    assert v.numbers["gap"] < 0, "the gap is negative by construction here"
    print("\nOK -- the tool caught it. Note that nothing about this index ERRORS:")
    print("     it returns a passage for every query, on time, every time.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
