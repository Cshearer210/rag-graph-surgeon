#!/usr/bin/env python3
# CALLED BY: .github/workflows/ci.yml, tests/test_examples_run.py, and by hand.
# FIRES WHEN: every push and pull request.
"""Run every example and fail if any of them does.

⛔ WHY CI RUNS THE EXAMPLES. An example that has quietly stopped working is worse than no example:
it is the first thing a stranger tries, and it fails in front of them rather than in front of us.
They are also the clearest statement of what this tool claims, so if one goes red the claim has
changed and the README probably needs to as well.

⚠ AND IT HAS ALREADY EARNED ITS PLACE. `honest_index.py` lost its `import random` while being
rewritten for this repo; every query raised `NameError`, and the tool -- correctly refusing to score
a probe that raised -- reported CANNOT TELL. The example's own assertion is what caught it, and the
verdict now names a raising `query_fn` instead of blaming the sample size.

    python3 examples/run_all.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Ordered so the story reads in the terminal: the two library judgements first, then the repair road.
EXAMPLES = [
    ("honest_index.py", "an index that works -- real questions above nonsense"),
    ("lying_index.py", "the real failure: nonsense at 0.735 beat real questions at 0.687"),
    ("flat_index.py", "the one most graders pass: every score identical, gap exactly 0"),
    ("refusing_index.py", "a refusal that looks like a perfect score, reported as a refusal"),
    ("should_i_fan_out.py", "six real dispatch decisions, and what it says about each"),
    ("before_after_demo.py", "the repair road: a broken shop, fixed, and a storefront shipped"),
]


def main():
    failed = []
    for name, what in EXAMPLES:
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            failed.append((name, "the file is missing"))
            print("MISSING  %-22s %s" % (name, what))
            continue
        r = subprocess.run([sys.executable, path], capture_output=True, text=True)
        ok = r.returncode == 0
        print("%s  %-22s %s" % ("ok      " if ok else "FAILED  ", name, what))
        if not ok:
            tail = (r.stdout + r.stderr).strip().splitlines()[-6:]
            for line in tail:
                print("            %s" % line)
            failed.append((name, "exit %d" % r.returncode))

    print()
    if failed:
        print("%d of %d example(s) FAILED: %s"
              % (len(failed), len(EXAMPLES), ", ".join(n for n, _ in failed)))
        return 1
    print("all %d examples ran clean." % len(EXAMPLES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
