# CALLED BY: `python3 -m ragghost <stage> <path>` -- the command the README tells a stranger to run.
# FIRES WHEN: asked -- it is the command line of a standalone tool.
"""The command line. Three outcomes, three exit codes, and it says which one it returned."""
from __future__ import annotations

import sys

from .scan import scan
from .graph import build_graph
from .organize import organize
from .retrieve import build_index
from .harness import harnesses
from .plan import plan
from .analyse import analyse
from .fix import fix

USAGE = """rag-ghost -- point it at a system and find out what is actually there

  python3 -m ragghost scan <path>       stage 1: discover everything, counted twice
  python3 -m ragghost graph <path>      stage 2: what is wired to what, both directions
  python3 -m ragghost organize <path>   stage 3: tiered index; what is load-bearing vs movable
  python3 -m ragghost retrieve <path>   stage 4: build the retrieval layer and audit that it works
  python3 -m ragghost harness <path>    stage 5: split into subsystems; flag any with no gate
  python3 -m ragghost plan <path>       stage 6: a harm-ranked plan from the real findings
  python3 -m ragghost analyse <path>    stage 7: decide if the work divides -- refuse a pointless fan-out
  python3 -m ragghost fix <path>        stage 8: dry-run the mechanical fixes (add --apply to write them)

Exit codes, and they are the point:
  0   it looked, and everything checks out
  1   it looked, and found something
  2   IT COULD NOT TELL -- never treat this as clean
"""

STAGES = {
    "scan": lambda path: scan(path),
    "graph": lambda path: build_graph(path),
    "organize": lambda path: organize(path),
    "retrieve": lambda path: build_index(path),
    "harness": lambda path: harnesses(path),
    "plan": lambda path: plan(path),
    "analyse": lambda path: analyse(path),
    "fix": lambda path, apply=False: fix(path, apply=apply),
}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        sys.stdout.write(USAGE)
        return 0
    cmd = argv[0]
    if cmd not in STAGES:
        sys.stdout.write("unknown command %r\n\n%s" % (cmd, USAGE))
        return 2
    apply = "--apply" in argv
    paths = [a for a in argv[1:] if not a.startswith("-")]
    if not paths:
        sys.stdout.write("%s needs a path.\n\n%s" % (cmd, USAGE))
        return 2
    result = STAGES[cmd](paths[0], apply=apply) if cmd == "fix" else STAGES[cmd](paths[0])
    result.report()
    return result.exit_code()


if __name__ == "__main__":
    sys.exit(main())
