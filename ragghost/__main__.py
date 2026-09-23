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
  python3 -m ragghost check <path>      all findings in one report -- for CI. --format text|json|sarif
  python3 -m ragghost demo              a 15-second self-contained demonstration

  Config: a .ragghost.json in the target root -- {"select":[...],"ignore":[...]} of codes.
  Silence one on a file: a line  # ragghost: allow <CODE>  in that file.
  Plugins: register a check under the "ragghost.checks" entry point, or a ragghost_plugin_* module.

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
    if cmd == "demo":
        from .demo import main as demo_main
        return demo_main(argv[1:])
    fmt = "text"
    for a in argv:
        if a.startswith("--format"):
            fmt = a.split("=", 1)[1] if "=" in a else (argv[argv.index(a) + 1] if argv.index(a) + 1 < len(argv) else "text")
    paths = [a for a in argv[1:] if not a.startswith("-") and a not in ("text", "json", "sarif")]
    if cmd == "check":
        if not paths:
            sys.stdout.write("check needs a path.\n\n%s" % USAGE)
            return 2
        from .report import check
        from .plugins import run_plugins
        result = check(paths[0], fmt=fmt if fmt in ("text", "json", "sarif") else "text",
                       extra_findings=run_plugins(paths[0]))
        result.report()
        return result.exit_code()
    if cmd not in STAGES:
        sys.stdout.write("unknown command %r\n\n%s" % (cmd, USAGE))
        return 2
    apply = "--apply" in argv
    if not paths:
        sys.stdout.write("%s needs a path.\n\n%s" % (cmd, USAGE))
        return 2
    result = STAGES[cmd](paths[0], apply=apply) if cmd == "fix" else STAGES[cmd](paths[0])
    result.report()
    return result.exit_code()


if __name__ == "__main__":
    sys.exit(main())
