# CALLED BY: `python3 -m ragghost ...` -- the command the README tells a stranger to run.
# FIRES WHEN: asked -- it is the command line of a standalone tool.
"""The command line. Three outcomes, three exit codes, and it says which one it returned."""
from __future__ import annotations

import sys

from .scan import scan

USAGE = """rag-ghost -- point it at a system and find out what is actually there

  python3 -m ragghost scan <path>      discover everything under <path>

Exit codes, and they are the point:
  0   it looked, and the population checks out
  1   it looked, and found something
  2   IT COULD NOT TELL -- never treat this as clean
"""


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        sys.stdout.write(USAGE)
        return 0
    if argv[0] != "scan":
        sys.stdout.write("unknown command %r\n\n%s" % (argv[0], USAGE))
        return 2
    if len(argv) < 2:
        sys.stdout.write("scan needs a path.\n\n%s" % USAGE)
        return 2
    r = scan(argv[1])
    r.report()
    code = r.exit_code()
    sys.stdout.write("\nexit %d -- %s\n" % (
        code, {0: "it looked, and the population checks out",
               1: "it looked, and found something",
               2: "IT COULD NOT TELL. This is not clean."}[code]))
    return code


if __name__ == "__main__":
    sys.exit(main())
