# CALLED BY: README.md quickstart + tests/test_demo.py (asserts BEFORE broken, AFTER fixed+shipped)
# FIRES WHEN: asked   the one polished before/after demo a viewer runs to see the surgeon work
"""RAG-Ghost — the one example, done well: a broken system, BEFORE and AFTER.

Point the surgeon at a shop that does not work — its data will not parse, a module imports a name
that is not there, files are dead weight — and watch it index the system, fix what it safely can,
hand the judgement calls back to the owner, and ship a working storefront it grades itself.

    python3 examples/before_after_demo.py            # run it and read the story
    python3 examples/before_after_demo.py --open      # also print the path to open the store

This is the selling point in one run: take a broken self-built system and get outputs flowing.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BROKEN = os.path.join(HERE, "broken-shop")

# ⛔ THE REPO ROOT GOES ON THE PATH BECAUSE THIS SCRIPT NOW IMPORTS THE PACKAGE, AND THAT IS NEW.
# It used to touch `ragghost` only through a subprocess (with cwd=REPO, which is why that worked from
# an uninstalled checkout), so `python3 examples/before_after_demo.py` never needed the import. The
# moment the output-type count started coming from the registry instead of being typed in prose, it
# did -- and the demo crashed after printing most of its story. Found by running it, not by reading
# it. With this line the demo works from a plain checkout and from an install alike.
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from ragghost.surgeon import builders            # noqa: E402  -- must follow the sys.path line above

# The planted defects, in plain words, so BEFORE is legible without reading the surgeon's output.
PLANTED = [
    ("data/products.json", "the product list has a trailing comma, so nothing can read it"),
    ("data/settings.json", "the settings file is empty — not even valid JSON"),
    ("data/config.json", "the store has no name set"),
    ("src/build_store.py", "imports a module 'templating' that does not exist (typo for 'template')"),
    ("src/discount_broken.py", "a Python syntax error — a human has to decide the intent"),
    ("src/legacy_paypal_ipn.py", "dead code nothing calls — a leftover"),
]


def _run_surgeon():
    ws = tempfile.mkdtemp(prefix="ragghost-demo-ws-")
    out = tempfile.mkdtemp(prefix="ragghost-demo-out-")
    r = subprocess.run(
        [sys.executable, "-m", "ragghost.surgeon", BROKEN,
         "--output", "landing", "--name", "Aurora Goods",
         "--out", out, "--workspace", ws, "--json"],
        cwd=REPO, capture_output=True, text=True)
    proof = None
    i = r.stdout.find("{")
    if i >= 0:
        try:
            proof = json.loads(r.stdout[i:])
        except json.JSONDecodeError:
            proof = None
    return r.returncode, proof, out


def _line(s=""):
    print(s)


def run(show_open=False):
    _line("=" * 70)
    _line("  RAG-Ghost — a broken system, fixed and shipping, in one run")
    _line("=" * 70)
    _line()
    _line("BEFORE — a self-built shop that does not work:")
    for path, why in PLANTED:
        _line("   x  %-26s %s" % (path, why))
    _line()
    _line("   Result today: the store cannot even load its own product list. Nothing ships.")
    _line()
    _line("Running the surgeon ...")
    _line()

    code, proof, out = _run_surgeon()
    if proof is None:
        _line("   the surgeon did not return a readable proof (exit %s)" % code)
        return 1

    fixed = proof.get("fixed", [])
    surfaced = proof.get("surfaced_for_owner", [])
    grade = proof.get("grade", {}) or {}
    shipped = proof.get("shipped")
    idx = proof.get("index", {}) or {}

    _line("AFTER — the surgeon read %d files, then:" % idx.get("files", 0))
    _line()
    _line("   FIXED automatically (%d):" % len(fixed))
    for item in fixed:
        finding, how = item if isinstance(item, (list, tuple)) else (item, "")
        _line("      +  %s" % _tidy(finding))
        _line("         -> %s" % how)
    _line()
    _line("   HANDED BACK to the owner to decide (%d) — never guessed at:" % len(surfaced))
    for item in surfaced:
        finding = item[0] if isinstance(item, (list, tuple)) else item
        _line("      ?  %s" % _tidy(finding))
    _line()

    # grade["score"] is a 0..1 fraction (checks passed / total); shipped means it cleared the bar.
    score = grade.get("score")
    checks = grade.get("checks", []) or []
    npass = sum(1 for c in checks if (c.get("ok") if isinstance(c, dict) else False))
    grade_str = ""
    if score is not None:
        grade_str = " — graded %d/100 (%d of %d checks) %s" % (
            round(score * 100), npass, len(checks), "PASS" if shipped else "below bar")
    _line("   SHIPPED: a working storefront%s" % grade_str)
    store_index = os.path.join(out, "index.html")
    # forward-slashed so the example prints the same thing on every platform -- an example
    # whose output changes shape on Windows is an example a stranger cannot compare to the README
    files = sorted(os.path.relpath(os.path.join(dp, f), out).replace(os.sep, "/")
                   for dp, _dn, fn in os.walk(out) for f in fn)
    _line("      %s" % ", ".join(f for f in files if f.endswith((".html", ".css", ".js"))))
    _line()
    # ⛔ THIS SAID "five output types" AND LISTED A SEPARATE "store" -- it was five until the
    # ecommerce builder was dropped, and the sentence did not go with it. A count typed into prose
    # cannot notice that the thing it counts has changed, which is the class of defect this very
    # demo exists to show off. So the number and the names now come from the registry itself and
    # cannot go stale again. Corrected 2026-09-27.
    kinds = sorted(builders.BUILDERS)
    _line("   The same run ships %d output types today — %s. `%s` is just this example."
          % (len(kinds), ", ".join(kinds[:-1]) + " or " + kinds[-1],
             proof.get("output") or "landing"))
    _line("   Point it at YOUR broken system to see it flow.")
    _line()
    if show_open and os.path.exists(store_index):
        _line("Open the shipped store:")
        _line("   %s" % store_index)
        _line()
    _line("=" * 70)
    _line("  broken -> fixed -> shipped, exit %d.  That is the whole product." % code)
    _line("=" * 70)
    return 0 if shipped else 1


def _tidy(finding):
    # findings look like "[fixable] broken-json  data/products.json  trailing comma..."; keep the readable half.
    s = str(finding)
    for tag in ("[fixable] ", "[SURFACE] "):
        s = s.replace(tag, "")
    return " ".join(s.split())


if __name__ == "__main__":
    sys.exit(run(show_open="--open" in sys.argv[1:]))
