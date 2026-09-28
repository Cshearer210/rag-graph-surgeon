# CALLED BY: surgeon/diagnose.py, surgeon/fix.py and all four builders in surgeon/builders/.
# FIRES WHEN: any of them needs to read a file out of a workspace. A library module, not a stage.
"""One definition of the handful of things every surgeon stage needs to read a workspace.

⛔ WHY THIS MODULE EXISTS. Stage 2's own duplicate-definition finder was pointed at this
repository and found its helpers copied across the tree: `_find` in all four builders,
byte-identical; `_slurp` in two; `_read` in diagnose and fix; and `grade_context` computing the
same display name two ways. A tool that reports "one job defined in two places" while its own
source does exactly that is the shape this repository has had to correct in itself once before.

⚠ THE MERGE TOOK THE BEST PART OF EACH COPY RATHER THAN PICKING A SURVIVOR, because the copies
had DRIFTED and each knew something the others did not:

  * `_load` existed in three versions -- `(ws, basename)` returning None, `(ws, basename, default)`
    returning a caller-chosen default, and `(ws, rel, default)` which called `os.path.basename` on
    its argument first. `load` below does all three: the default is a parameter, and the basename
    is always taken, which is a no-op for the callers that already passed one.
  * only the API builder's title logic guarded against a `config.json` that parses to something
    other than a dict -- a list, or a bare string. That guard is kept for everybody, so the other
    three no longer crash on a config the API builder survived.
"""
from __future__ import annotations

import json
import os

__all__ = ["SKIP", "read_text", "find", "load", "slurp", "display_name"]

# directories no workspace read should ever descend into
SKIP = {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}


def read_text(root, rel):
    """The text of `rel` under `root`. Never guesses an encoding, never silently returns ''."""
    return open(os.path.join(root, rel), encoding="utf-8", errors="replace").read()


def find(ws, basename):
    """The shallowest file named `basename` under `ws`, or None.

    Shallowest on purpose: a workspace usually holds the real `config.json` at its root and a
    fixture copy of the same name somewhere deep, and taking the deep one silently builds the
    output from a fixture.
    """
    root_hit = os.path.join(ws, basename)
    if os.path.exists(root_hit):
        return root_hit
    best, best_depth = None, 1 << 30
    for dp, dn, fn in os.walk(ws):
        dn[:] = [d for d in dn if d not in SKIP and not d.startswith(".")]
        if basename in fn:
            depth = dp[len(ws):].count(os.sep)
            if depth < best_depth:
                best, best_depth = os.path.join(dp, basename), depth
    return best


def load(ws, name, default=None):
    """Parse a JSON file out of the workspace, or hand back `default`.

    `name` may be a bare basename or a relative path; only its basename is searched for.
    Unparseable JSON returns the default rather than raising -- a broken config is a diagnosis
    the DIAGNOSE stage reports, not a crash in the middle of a build.
    """
    p = find(ws, os.path.basename(name))
    try:
        return json.load(open(p, encoding="utf-8")) if p and os.path.exists(p) else default
    except json.JSONDecodeError:
        return default


def slurp(out_dir, name):
    """The text of a BUILT artefact, or '' when it was not built. Used by the graders, where an
    absent file means the check fails rather than the run crashing."""
    p = os.path.join(out_dir, name)
    return open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else ""


def display_name(ws, scope, fallback):
    """What to call this thing on the page: the config's name, then the scope's, then `fallback`.

    The `isinstance` guard is not decoration -- `config.json` is a file a stranger's broken system
    supplies, and it is not always an object.
    """
    cfg = load(ws, "config.json", {})
    from_cfg = cfg.get("store_name") if isinstance(cfg, dict) else None
    return from_cfg or scope.get("store_name") or fallback


def name_context(key, fallback):
    """The grader's context function for a builder whose only difference is the key it reports
    under and the name it falls back on.

    ⚠ THIS EXISTS BECAUSE THE FIRST PASS OF THE DE-DUPLICATION DID NOT GO FAR ENOUGH, and stage 2
    said so. Folding the lookup into `display_name` left three builders each holding a one-line
    wrapper that differed only in two constants, and the duplicate finder reported them --
    correctly. Two constants are DATA; three copies of a function to carry them are not.
    """
    def grade_context(ws, scope):
        return {key: display_name(ws, scope, fallback)}
    return grade_context


def selftest() -> int:
    import tempfile
    ok = fail = 0

    def chk(name, cond):
        nonlocal ok, fail
        print("  %-52s %s" % (name[:52], "PASS" if cond else "FAIL"))
        ok, fail = ok + bool(cond), fail + (not cond)

    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "deep", "nested"))
    open(os.path.join(d, "config.json"), "w").write('{"store_name": "Aurora"}')
    open(os.path.join(d, "deep", "nested", "config.json"), "w").write('{"store_name": "Fixture"}')
    open(os.path.join(d, "bad.json"), "w").write("{not json")
    open(os.path.join(d, "list.json"), "w").write("[1, 2, 3]")

    chk("find prefers the shallowest match", find(d, "config.json") ==
        os.path.join(d, "config.json"))
    chk("find returns None when absent", find(d, "nope.json") is None)
    chk("load parses", load(d, "config.json", {}).get("store_name") == "Aurora")
    chk("load takes a relative path, not just a basename",
        load(d, "some/where/config.json", {}).get("store_name") == "Aurora")
    chk("load defaults to None when no default is given", load(d, "nope.json") is None)
    chk("broken JSON returns the default, never raises", load(d, "bad.json", {"d": 1}) == {"d": 1})
    chk("slurp of an unbuilt artefact is '' ", slurp(d, "index.html") == "")
    chk("read_text reads", "Aurora" in read_text(d, "config.json"))
    chk("display_name prefers the config", display_name(d, {}, "X") == "Aurora")
    chk("display_name falls back to the scope",
        display_name(os.path.join(d, "deep", "nested", "nothing"),
                     {"store_name": "FromScope"}, "X") == "FromScope")
    chk("display_name falls back to the fallback",
        display_name(os.path.join(d, "deep", "nested", "nothing"), {}, "X") == "X")
    # the guard the API builder had and the others did not: a config.json that is not an object
    os.makedirs(os.path.join(d, "listy"))
    open(os.path.join(d, "listy", "config.json"), "w").write("[1, 2, 3]")
    chk("a config.json that is a LIST does not crash display_name",
        display_name(os.path.join(d, "listy"), {}, "Fallback") == "Fallback")
    chk("name_context reports under the key it was given",
        name_context("title", "X")(d, {}) == {"title": "Aurora"})
    chk("name_context carries its own fallback",
        name_context("name", "Fallback")(os.path.join(d, "nowhere"), {}) == {"name": "Fallback"})
    print("\n  %d passed, %d failed" % (ok, fail))
    return 1 if fail else 0


if __name__ == "__main__":
    import sys
    sys.exit(selftest())
