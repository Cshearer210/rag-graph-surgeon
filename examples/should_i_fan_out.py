#!/usr/bin/env python3
"""The other half of the tool: four real dispatch decisions, and what it says about each.

Every row below is a decision somebody actually had to make. The last one is the expensive one.

Run:  python examples/should_i_fan_out.py     ->  exit 0
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))      # the repo root, so a checkout needs no install

from ragghost import fanout                                             # noqa: E402

DECISIONS = [
    ("Triage 400 transcripts, each judged on its own",
     dict(shape="population", items=400), 0),
    ("Have 5 reviewers score one design without seeing each other",
     dict(shape="independent-opinions", items=5), 0),
    ("Merge 26 findings from 7 agents into one answer",
     dict(shape="synthesis", items=26), 1),
    ("Re-run a path we already recorded, on 50 files",
     dict(shape="known-path", items=50), 1),
    ("Fan out over 40 items with the cap left at 0",
     dict(shape="population", items=40, cap=0), 1),
    ("'Make it faster' -- nobody named the shape",
     dict(shape="make it faster"), 2),
]


def main():
    wrong = 0
    for label, kw, want in DECISIONS:
        a = fanout.advise(**kw)
        mark = "ok " if a.code == want else "BAD"
        if a.code != want:
            wrong += 1
        print("%s  %-52s -> %s" % (mark, label[:52], a.headline[:58]))
    print()
    print("The one that cost real money: a 7-agent fan-out produced 26 findings, 78 agents")
    print("were then spawned to verify them, and 3 were confirmed. 17.0M tokens, 4.1 hours.")
    print("Reading the same material in ONE context found the same 3 for a fiftieth of it.")
    print("`synthesis` is row 3 above, and it is the row that was ignored.")
    assert wrong == 0, "%d decision(s) came back with the wrong code" % wrong
    return 0


if __name__ == "__main__":
    sys.exit(main())
