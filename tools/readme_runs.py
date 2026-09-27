#!/usr/bin/env python3
# CALLED BY: .github/workflows/ci.yml and tests/test_readme_runs.py
# FIRES WHEN: every push and pull request.
# ragghost: allow GRAPH-ORPHAN  -- a standalone CI/operator script, not imported by the package
"""Type what the README tells a stranger to type, and fail if it does not behave as documented.

⛔ WHY THIS EXISTS. The README is the one file every stranger reads and the one file no test touches,
so it rots silently and then fails in front of the person you most wanted to impress. It had already
drifted twice in this repo within a day: a test count was typed at 355 when the real figure was 354,
and a coverage figure at 84% when it was 87% — both written from memory in a file whose whole subject
is that a document describing a system is evidence about the past.

⭐ AND THE EXPECTED EXIT CODE IS PART OF THE DOCUMENTATION, WHICH IS THE POINT. Several commands below
are SUPPOSED to exit non-zero — that is what the README is demonstrating. A checker that simply
asserted "exit 0" would call the tool broken for doing exactly the thing it is being shown doing. The
first version of this idea, in the tree this came from, did precisely that and reported 3 of 5
commands failing, all three of them correct.

⚠ IT ALSO CHECKS THE NUMBERS, not only the commands. A command that runs is not a README that is
true: `--tests` re-counts what pytest collects and compares it to the figure the README prints, and
the same for the coverage total when `coverage` is installed. A typed count in a document cannot
notice it has gone wrong, so something else has to.

    python3 tools/readme_runs.py            # the commands, and the numbers it can check for free
    python3 tools/readme_runs.py --tests    # also re-count the tests and verify the README's figure
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable

# (argv after the interpreter, expected exit code, why that code is the documented behaviour)
#
# Deliberately NOT included: `pip install git+https://...`, which needs the network and would make
# this check fail for a reason that has nothing to do with the README being right.
CASES = [
    (["-m", "ragghost", "--help"], 0, "the help text prints on this console, markers and all"),
    (["-m", "ragghost", "doctor"], 0, "the install verifies itself: 6 checks, all must pass"),
    (["-m", "ragghost", "demo"], 0, "the 15-second tour the README shows verbatim"),
    (["-m", "ragghost", "check", "."], 0,
     "the README claims this repo holds itself to its own standard and exits 0"),
    (["-m", "ragghost", "check", ".", "--format", "json"], 0, "the JSON form the README offers"),
    (["-m", "ragghost", "check", ".", "--format", "sarif"], 0, "the SARIF form the README offers"),
    (["-m", "ragghost", "shapes"], 0, "the shapes listing"),
    (["-m", "ragghost", "fanout", "synthesis", "--items", "26"], 1,
     "the README shows this REFUSING -- exit 1 is the documented answer, not a failure"),
    (["-m", "ragghost", "fanout", "make it fast"], 2,
     "an unnamed shape is CANNOT TELL -- exit 2, and never a yes"),
    (["-m", "ragghost", "fanout", "population", "--items", "400"], 0,
     "a population too big for one context is approved"),
    (["examples/run_all.py"], 0, "every example the README points at still runs"),
    (["tools/run_against_real_index.py"], 2,
     "with no index named it is CANNOT TELL -- a run that never reached an index has no opinion"),
]

# A stage the README's minimal example shows, run against a system built here rather than against
# this repo, so the expected code is not hostage to this repo's own state.
SYNTHETIC_STAGES = [("scan", 0), ("graph", 1), ("plan", 1)]


def _readme():
    return open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()


def _run(argv, cwd=ROOT):
    return subprocess.run([PY] + argv, cwd=cwd, capture_output=True, text=True, timeout=900)


def check_commands():
    """Every documented command, with its documented exit code. -> [failure strings]"""
    fails = []
    for argv, want, why in CASES:
        r = _run(argv)
        if r.returncode != want:
            fails.append("`%s` exited %d, the README documents %d (%s)\n        %s"
                         % (" ".join(argv), r.returncode, want, why,
                            (r.stderr or r.stdout or "").strip().splitlines()[-1:] or [""]))
        # a crash is a different failure from an honest non-zero exit, and it hides inside one
        if "Traceback (most recent call last)" in (r.stderr or ""):
            fails.append("`%s` printed a TRACEBACK -- its exit code may be right by accident"
                         % " ".join(argv))
    return fails


def check_synthetic_stages():
    """A built-here system with a planted orphan: scan clean, graph and plan find it."""
    fails = []
    d = tempfile.mkdtemp(prefix="ragghost-readme-")
    open(os.path.join(d, "main.py"), "w").write("A = 1\n")
    open(os.path.join(d, "orphan.py"), "w").write("B = 2\n")
    for stage, want in SYNTHETIC_STAGES:
        r = _run(["-m", "ragghost", stage, d])
        if r.returncode != want:
            fails.append("stage `%s` on a system with one planted orphan exited %d, expected %d"
                         % (stage, r.returncode, want))
    return fails


def check_numbers(recount=False):
    """The figures the README prints, compared with what the machine says. -> [failure strings]

    ⛔ A TYPED COUNT IN A DOCUMENT CANNOT NOTICE IT HAS GONE WRONG. That is this repo's own law about
    other people's code, so it applies hardest here.
    """
    fails, text = [], _readme()

    m = re.search(r"#\s*(\d[\d,]*)\s+tests,\s+standard library", text)
    if not m:
        fails.append("the README no longer states its test count in the form '# N tests, standard "
                     "library ...' -- either restore it or update this check, but do not leave the "
                     "number unverifiable")
    elif recount:
        claimed = int(m.group(1).replace(",", ""))
        r = _run(["-m", "pytest", "-q", "--collect-only"])
        got = len(re.findall(r"^\S+::", r.stdout, re.M)) or None
        if got is None:
            mm = re.search(r"(\d+)\s+tests? collected", r.stdout)
            got = int(mm.group(1)) if mm else None
        if got is None:
            fails.append("could not re-count the tests, so the README's %d is UNVERIFIED -- which "
                         "is not the same as wrong, and is reported rather than assumed fine"
                         % claimed)
        elif got != claimed:
            fails.append("the README says %d tests; pytest collects %d" % (claimed, got))

    # ⚠ TOLERANT OF THE PROSE, STRICT ABOUT THE NUMBER. The first version required the bolded span to
    # end exactly `by line**`, and the README wrote `by line.**` -- so it reported a figure as
    # unverifiable when it was sitting right there. A checker that fires on punctuation teaches
    # everyone to ignore it, which is worse than not having one.
    m = re.search(r"\*\*(\d{1,3})%\s+of\s+(?:\n\s*)?the package by line[.,:;]?\*\*", text)
    if not m:
        fails.append("the README no longer states a coverage percentage in a form this can find")
    elif recount:
        try:
            import coverage                                            # noqa: F401
        except ImportError:
            print("  note: coverage is not installed here, so the README's %s%% is UNVERIFIED "
                  "rather than confirmed" % m.group(1))
        else:
            subprocess.run([PY, "-m", "coverage", "run", "-m", "pytest", "-q"],
                           cwd=ROOT, capture_output=True, text=True, timeout=1800)
            rep = subprocess.run([PY, "-m", "coverage", "report"], cwd=ROOT,
                                 capture_output=True, text=True, timeout=300)
            tm = re.search(r"^TOTAL\s+\d+\s+\d+\s+(\d+)%", rep.stdout, re.M)
            if tm and int(tm.group(1)) != int(m.group(1)):
                fails.append("the README says %s%% coverage; coverage reports %s%%"
                             % (m.group(1), tm.group(1)))
    return fails


def check_links():
    """Every relative path the README points at exists. A dead link in the front door is the
    GRAPH-DANGLING class this tool advertises, in the file a stranger reads first."""
    fails, text = [], _readme()
    for rel in set(re.findall(r"\]\((?!https?:)([^)#]+)\)", text)):
        if not os.path.exists(os.path.join(ROOT, rel.strip())):
            fails.append("the README links to %r and it does not exist" % rel.strip())
    return fails


def main(argv=None):
    ap = argparse.ArgumentParser(description="Does the README still describe this tool?")
    ap.add_argument("--tests", action="store_true",
                    help="also re-count the tests and re-measure coverage (slower)")
    a = ap.parse_args(argv)

    groups = [("documented commands", check_commands()),
              ("documented stage exit codes", check_synthetic_stages()),
              ("relative links", check_links()),
              ("typed numbers", check_numbers(recount=a.tests))]
    total = 0
    for name, fails in groups:
        print("  %-30s %s" % (name, "ok" if not fails else "%d FAILURE(S)" % len(fails)))
        for f in fails:
            print("      %s" % f)
        total += len(fails)
    print()
    if total:
        print("the README does not describe this tool any more: %d failure(s)." % total)
        return 1
    print("the README's own commands all behave as it documents them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
