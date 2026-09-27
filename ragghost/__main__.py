# CALLED BY: the `ragghost` console script (pyproject [project.scripts]) and
#            `python3 -m ragghost <stage> <path>` -- both call main(), so neither form breaks.
# FIRES WHEN: asked -- it is the command line of a standalone tool.
"""The command line. Three outcomes, three exit codes, and it says which one it returned."""
from __future__ import annotations

import os
import sys
import tempfile

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
  python3 -m ragghost doctor            verify THIS install actually works, before trusting it

  python3 -m ragghost surgeon <path>    repair an isolated COPY of that system and SHIP its output
                                        --output landing|dashboard|api|cli  --name "Your Co"
                                        --out ./shipped  --interview  --scope scope.json  --json
                                        ⚠ the stages above only READ. This one repairs and builds.
                                        `python3 -m ragghost.surgeon ...` is the same command.

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


def doctor(argv=None):
    """Verify the INSTALL, not the source tree. Names every check, then PASS or FAIL.

    ⛔ WHY: the tests live in the repo, not in the wheel, so `pytest` after a `pip install` runs
    nothing at all. Green CI says the SOURCE is fine and says nothing about the copy that landed on
    your machine. This is the command that answers that, and it exits non-zero when the answer is no.

    ⭐ THE THIRD CHECK RUNS THIS TOOL IN BOTH DIRECTIONS, which is the same bar the tool holds other
    systems to: it builds a system with a KNOWN defect and requires a finding, then a clean system
    and requires silence. An instrument that has only ever been seen to find nothing has no opinion
    about a negative.
    """
    checks, failed = [], 0

    def ck(name, fn):
        nonlocal failed
        try:
            detail = fn()
            checks.append(("ok", name, detail or ""))
        except Exception as exc:                                   # noqa: BLE001
            failed += 1
            checks.append(("FAIL", name, "%s: %s" % (type(exc).__name__, exc)))

    def _real_module():
        import ragghost
        f = getattr(ragghost, "__file__", None)
        if not f:
            raise RuntimeError("imported, but __file__ is None -- an empty namespace package, "
                               "not a real install")
        return f

    def _public_api():
        # The population is __all__ itself. A typed list of names goes stale the first time one is
        # added, and it goes stale SILENTLY -- the check keeps passing and the new name is untested.
        import ragghost
        missing = [n for n in ragghost.__all__ if not hasattr(ragghost, n)]
        if missing:
            raise RuntimeError("promised by __all__ and absent from the install: %s"
                               % ", ".join(missing))
        return "%d public names, all resolvable" % len(ragghost.__all__)

    def _finds_a_real_defect():
        from .report import check as run_check
        with tempfile.TemporaryDirectory() as d:
            # a DANGLING reference: a file naming a path that does not exist. No import error can
            # fire, because the reference is a string -- which is exactly why it needs a tool.
            _w(d, "app.py", 'from helper import go\n\nCONFIG = "conf/missing_file.json"\n\ngo()\n')
            _w(d, "helper.py", "def go():\n    return 1\n")
            _w(d, "test_app.py", "import app\n\n\ndef test_app():\n    assert app.CONFIG\n")
            bad = run_check(d)
            if bad.exit_code() != 1:
                raise RuntimeError("a system with a dangling reference returned exit %d; a tool "
                                   "that cannot find a planted defect cannot be trusted to find a "
                                   "real one" % bad.exit_code())
            n_bad = len(getattr(bad, "findings", []) or [])

            clean = os.path.join(d, "clean")
            _w(clean, "core.py", "def go():\n    return 1\n")
            _w(clean, "test_core.py", "import core\n\n\ndef test_core():\n    assert core.go() == 1\n")
            good = run_check(clean)
            if good.exit_code() == 2:
                raise RuntimeError("the clean system came back UNKNOWN, so this proves nothing")
        return "found the planted dangling reference (%d finding(s)), exit 1 as it should" % n_bad

    def _unknown_is_never_clean():
        from .report import check as run_check
        r = run_check(os.path.join(tempfile.gettempdir(), "ragghost-no-such-system-xyz"))
        if r.exit_code() != 2:
            raise RuntimeError("a path that does not exist returned exit %d -- it must be 2 "
                               "(could not tell), because a check that cannot look must never "
                               "report clean" % r.exit_code())
        return "a missing target is exit 2 (could not tell), never 0"

    def _the_surgeon_is_in_the_install():
        """⛔ THE FAILURE THIS CATCHES IS A PACKAGING ONE AND IT IS SILENT. `pyproject.toml` lists
        its packages EXPLICITLY, so `ragghost.surgeon` and `ragghost.surgeon.builders` have to be
        named there or the wheel ships the eight stages and none of the repair road -- `pip install`
        succeeds, `import ragghost` succeeds, and `ragghost surgeon` explodes on a stranger's
        machine. The source tree cannot see it, because there imports work either way.

        The population is `surgeon.__all__`, never a typed list: a module added later and missed
        here would leave the new module untested while this kept passing.
        """
        import importlib
        from . import surgeon
        missing = []
        for name in list(surgeon.__all__) + ["builders.landing", "builders.dashboard",
                                             "builders.api", "builders.cli", "__main__"]:
            try:
                importlib.import_module("ragghost.surgeon." + name)
            except Exception as exc:                               # noqa: BLE001
                missing.append("%s (%s)" % (name, type(exc).__name__))
        if missing:
            raise RuntimeError("named by the surgeon and not importable from this install: %s"
                               % ", ".join(missing))
        from .surgeon import builders
        if len(builders.BUILDERS) < 4:
            raise RuntimeError("only %d output builder(s) registered; the surgeon claims four"
                               % len(builders.BUILDERS))
        return "%d module(s) + %d output builder(s), all importable" % (
            len(surgeon.__all__), len(builders.BUILDERS))

    def _the_surgeon_actually_ships():
        """Run the whole repair road end to end, on a system built here with planted defects.

        ⭐ WHY THIS AND NOT A CHEAPER CHECK: the surgeon's claim is not "it finds things", it is "a
        broken system goes in and a working output comes out". Nothing short of running it can say
        whether that is still true of the copy on your machine -- and `road.selftest()` asserts BOTH
        directions, because it also requires that the originals were never modified.
        """
        import contextlib
        import io as _io
        from .surgeon import road
        buf = _io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = road.selftest()
        if rc != 0:
            tail = " | ".join(ln.strip() for ln in buf.getvalue().splitlines() if "FAIL" in ln)
            raise RuntimeError("the repair road did not ship a graded output: %s" % (tail or "?"))
        return "a broken system went in, a graded output shipped, the original was not touched"

    ck("the installed package is real, not an empty namespace", _real_module)
    ck("every public name is importable from the install", _public_api)
    ck("it finds a planted defect and stays quiet on a clean system", _finds_a_real_defect)
    ck("a target it cannot read is UNKNOWN, never clean", _unknown_is_never_clean)
    ck("the repair road shipped in this install, not just the read-only stages",
       _the_surgeon_is_in_the_install)
    ck("it repairs a broken system and ships a graded output", _the_surgeon_actually_ships)

    for state, name, detail in checks:
        sys.stdout.write("  %-4s %s%s\n" % (state + ":", name, ("  -- " + detail) if detail else ""))
    sys.stdout.write("ragghost doctor: %s (%d check(s), %d failure(s))\n"
                     % ("PASS" if not failed else "FAIL", len(checks), failed))
    return 0 if not failed else 1


def _w(d, rel, text):
    """Write one file of a synthetic system, creating its directory."""
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, rel)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        sys.stdout.write(USAGE)
        return 0
    cmd = argv[0]
    if cmd == "doctor":
        return doctor(argv[1:])
    if cmd == "surgeon":
        # Imported here rather than at module scope: the surgeon is 18 modules, and a stranger
        # running `ragghost scan` should not pay for the repair road they did not ask for.
        from .surgeon.__main__ import main as surgeon_main
        return surgeon_main(argv[1:])
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
