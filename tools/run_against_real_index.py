#!/usr/bin/env python3
# CALLED BY: a human, deliberately, against their own index. Not imported by the package and not
#            run in CI -- there is no real index on a CI runner, and pretending otherwise would be
#            the fake measurement this whole tool exists to find.
# FIRES WHEN: asked.
# ragghost: allow GRAPH-ORPHAN  -- a standalone operator script, not imported on purpose (same as
#                                 tools/render_demo_svg.py beside it)
"""Point ragghost at YOUR live retrieval index and report whichever way it comes out.

    python3 tools/run_against_real_index.py --module my_index --path ./src

⭐ THIS IS THE STEP THAT MAKES THE TOOL HONEST. The test suite proves the tool is internally
consistent and says NOTHING about whether its verdict is true of a real system. So it gets aimed at
a live index, and the result is written down whichever way it lands -- including "this index is fine
and the tool found nothing", which is a real outcome and not a failure.

⛔ WHAT IT FOUND THE FIRST TIME IT WAS RUN, against a real embedding index of 82,000+ chunks: random
hexadecimal scored **0.735** while real questions scored **0.687**. Nonsense outranked meaning. Every
answer built on that index came back confident and nothing anywhere raised an error. That exact pair
is the first case in `tests/test_ranks_meaning.py`, and `examples/lying_index.py` reproduces it with
no index at all.

⛔ AND THE REAL QUESTIONS MUST NOT BE INVENTED. Supply phrases someone would actually type at your
system, each with an answer you already know, so a miss is a RETRIEVAL failure rather than a wording
mismatch. A question set written by whoever wrote the corpus tests the corpus against itself.

HOW TO ADAPT IT: the only thing this file really contains is `build_query_fn` -- a few lines turning
whatever your retrieval system returns into a score. Everything else is argument parsing. If your
index is not an importable Python module, ignore the plumbing and call
`ragghost.ranks_meaning.judge(your_function, your_questions)` directly.
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))          # the repo root, so a checkout needs no install

import ragghost                                                         # noqa: E402
from ragghost import ranks_meaning                                      # noqa: E402

# Replace these with questions someone would actually type at YOUR system, each with an answer you
# already know. Deliberately varied in shape: some keyword-ish, some full sentences, some using words
# the corpus does NOT use -- an index that only answers questions phrased in its own vocabulary has
# not been tested.
REAL_QUESTIONS = [
    "how do I set the pump pressure",
    "what solvent ratio for a winterization",
    "cold trap temperature",
    "why did the column clog",
    "how long to purge",
    "what causes a cloudy extract",
    "vacuum depth for terpene recovery",
    "when to change the desiccant",
    "filter micron for a first pass",
    "how to calibrate the gauge",
    "what is a proper flush volume",
    "signs of a failed seal",
]


def build_query_fn(mod):
    """-> query(text) -> (score, path). The ONLY adapter this tool needs.

    Assumes `mod.query(text, k=1)` returns `(code, rows, note)` with rows carrying `score` and
    `meta.path`. Yours will differ -- this function is the part you rewrite, and it is a few lines.

    ⛔ A NON-ANSWER RETURNS None, NEVER A LOW SCORE. An index that did not answer has not scored the
    probe low, and treating silence as a zero manufactures a clean result out of a broken index.
    """
    def query_fn(text):
        code, rows, _note = mod.query(text, k=1)
        if code != 0 or not rows:
            return None, None
        row = rows[0]
        return row.get("score"), (row.get("meta") or {}).get("path")
    return query_fn


def main(argv=None):
    ragghost.console_safe()
    ap = argparse.ArgumentParser(description="Audit YOUR live retrieval index.")
    ap.add_argument("--module", default=os.environ.get("RAGGHOST_INDEX_MODULE", ""),
                    help="importable module exposing query(text, k) (env: RAGGHOST_INDEX_MODULE)")
    ap.add_argument("--path", default=os.environ.get("RAGGHOST_INDEX_PATH", ""),
                    help="directory to add to sys.path first (env: RAGGHOST_INDEX_PATH)")
    ap.add_argument("--probes", type=int, default=18)
    ap.add_argument("--seed", type=int, default=20260920)
    a = ap.parse_args(argv)

    if not a.module:
        # ⛔ CANNOT TELL, never a pass. A run that never reached an index has no opinion about one,
        # and exiting 0 here would be the exact failure this tool is named after.
        print("CANNOT TELL: no index named. Point it at yours:")
        print("    python3 tools/run_against_real_index.py --module my_index --path ./src")
        print("Or skip the plumbing and call ragghost.ranks_meaning.judge(your_fn, your_questions).")
        print("For a version that needs no index at all, see examples/.")
        return 2

    if a.path:
        sys.path.insert(0, os.path.expanduser(a.path))
    try:
        mod = importlib.import_module(a.module)
    except Exception as e:                                              # noqa: BLE001
        print("CANNOT TELL: %r would not import (%s: %s)" % (a.module, type(e).__name__, e))
        return 2
    if not hasattr(mod, "query"):
        print("CANNOT TELL: %r has no query(); rewrite build_query_fn for your system" % a.module)
        return 2

    print("Running ragghost against %s..." % a.module)
    print("  %d real questions, %d nonsense probes generated at runtime in 3 shapes"
          % (len(REAL_QUESTIONS), a.probes))
    print()
    v = ranks_meaning.judge(build_query_fn(mod), REAL_QUESTIONS, n=a.probes, seed=a.seed)
    print(v)
    print()
    print("exit code %d  (0 clean / 1 found a problem / 2 cannot tell)" % v.code)
    return v.code


if __name__ == "__main__":
    sys.exit(main())
