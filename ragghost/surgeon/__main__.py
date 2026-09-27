"""CLI: point the surgeon at a broken system and get an output flowing.

    python -m ragghost.surgeon <target> --out ./shipped
    python -m ragghost.surgeon <target> --scope scope.json --out ./shipped
    python -m ragghost.surgeon <target> --output landing --name "Aurora" --out ./shipped
    python -m ragghost.surgeon <target> --interview        # ask me the questions

Exit code: 0 shipped and graded clean, 1 shipped-below-bar or blocked, 2 bad input.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

from . import interview, road


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ragghost.surgeon",
                                 description="Fix a broken self-built system and ship its output.")
    ap.add_argument("target", help="path to the (possibly broken) system")
    ap.add_argument("--out", default="./surgeon-output", help="where the shipped output goes")
    ap.add_argument("--workspace", default=None, help="isolated workspace dir (default: a temp dir)")
    ap.add_argument("--scope", help="scope.json describing goal/output")
    ap.add_argument("--output", help="output type to ship (landing, dashboard, api, cli)")
    ap.add_argument("--name", help="store/product name")
    ap.add_argument("--interview", action="store_true", help="ask the scope questions interactively")
    ap.add_argument("--memory", default=None, help="path to the surgeon's memory file")
    ap.add_argument("--json", action="store_true", help="print the proof as JSON")
    a = ap.parse_args(argv)

    if not os.path.isdir(a.target):
        print("target is not a directory: %s" % a.target, file=sys.stderr)
        return 2

    if a.scope:
        sc = interview.Scope.from_file(a.scope)
    elif a.interview:
        sc = interview.interview(interactive=True)
    else:
        sc = interview.interview(interactive=False)
    if a.output:
        sc.output = a.output
    if a.name:
        sc.store_name = a.name
        sc.defaults["store_name"] = a.name

    ws = a.workspace or os.path.join(tempfile.mkdtemp(), "workspace")
    r = road.run(a.target, ws, a.out, scope=sc, mem_path=a.memory, verbose=not a.json)

    if a.json:
        print(json.dumps(r.proof(), indent=2))
    else:
        print("\n" + "=" * 60)
        print("SHIPPED" if r.shipped else "BLOCKED (below grading bar)")
        print("  output:   %s -> %s" % (r.output, r.output_dir))
        print("  fixed:    %d issue(s)" % len(r.fixed))
        print("  surfaced: %d for you to decide" % len(r.surfaced))
        print("  grade:    %.0f%%" % (r.grade_score * 100))
        print("  proof:    %s" % os.path.join(r.output_dir, "_surgeon_proof.json"))
    return 0 if r.shipped else 1


if __name__ == "__main__":
    sys.exit(main())
