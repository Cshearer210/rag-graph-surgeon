# CALLED BY: ragghost/__main__.py  (`python3 -m ragghost organize <path>`)
# FIRES WHEN: asked -- a library module of a standalone tool, run by whoever downloaded it.
"""STAGE 3 -- ORGANIZE. Sort the system into a tiered structure, and INDEX what must not move.

⛔ THE FAILURE THIS STAGE EXISTS FOR: the obvious way to tidy a system is to MOVE files into a
neat layout -- and moving a file that something references by path or imports by location breaks
it silently, which is the exact failure stage 2 exists to catch. So this stage does NOT move
anything. It builds a tiered INDEX over the files where they already sit, and it marks every file
PINNED (something depends on it, so moving it would break that) or MOVABLE (nothing references it,
so it could be reorganised safely). Indexing what must not move is safer than moving it.

It also flags files that are clearly misfiled by a rule nobody disputes -- a test file outside any
tests directory -- because that is organisation drift a person can act on without risk.

No dependencies, no network. It reads; it never writes to the target.
"""
from __future__ import annotations

import ast
import os
import sys

from .graph import build_graph
from .scan import KINDS

__all__ = ["organize", "Index"]


def _kind_of(ext):
    for kind, exts in KINDS.items():
        if ext in exts:
            return kind
    return "other"


def _tier(path, is_imported):
    base = os.path.basename(path)
    ext = os.path.splitext(base)[1].lower()
    if base in ("__main__.py", "cli.py", "setup.py", "main.py"):
        return "entry"
    if base.startswith("test_") or "/tests/" in path or path.startswith("tests/"):
        return "test"
    kind = _kind_of(ext)
    if kind == "code":
        return "core" if is_imported else "leaf"
    return kind


class Index:
    """A tiered view of the system, plus which files are load-bearing (pinned) where they sit."""

    def __init__(self):
        self.root = ""
        self.tiers = {}            # tier -> [files]
        self.pinned = {}           # file -> [things that depend on it]  (must not move)
        self.movable = []          # files nothing references -> safe to reorganise
        self.misfiled = []         # (file, why) -- a clear, low-risk organisation fix
        self.hollow = []           # (package, why) -- declared subsystem holding nothing
        self.total = 0

    def exit_code(self):
        if not self.total:
            return 2                       # nothing to index -> UNKNOWN, never clean
        if self.misfiled or self.hollow:
            return 1
        return 0

    def report(self, out=sys.stdout):
        w = out.write
        w("ORGANIZE  %s\n" % self.root)
        w("=" * 70 + "\n")
        if not self.total:
            w("  NOTHING TO INDEX. UNKNOWN, not clean.\n")
            return
        w("  %d file(s) indexed in place -- nothing was moved.\n" % self.total)
        w("\n  TIERED VIEW\n")
        for tier in ("entry", "core", "leaf", "config", "docs", "data", "web", "media",
                     "test", "other"):
            files = self.tiers.get(tier, [])
            if files:
                w("    %-8s %5d\n" % (tier, len(files)))
        w("\n  LOAD-BEARING -- %d file(s) other files depend on (indexed, must not move)\n"
          % len(self.pinned))
        for f, deps in sorted(self.pinned.items(), key=lambda kv: -len(kv[1]))[:8]:
            w("    %-52s %d dependent(s)\n" % (f[:52], len(deps)))
        w("\n  SAFE TO REORGANISE -- %d file(s) nothing references\n" % len(self.movable))
        if self.hollow:
            w("\n  ⛔ %d DECLARED SUBSYSTEM(S) WITH NOTHING IN THEM -- UNKNOWN, not clean\n"
              % len(self.hollow))
            for d, why in self.hollow[:12]:
                w("    %-52s %s\n" % (d[:52], why))
        if self.misfiled:
            w("\n  ⛔ %d FILE(S) CLEARLY MISFILED -- a low-risk tidy\n" % len(self.misfiled))
            for f, why in self.misfiled[:12]:
                w("    %-52s %s\n" % (f[:52], why))
        else:
            w("\n  No file is clearly misfiled.\n")


def _is_empty_module(abs_path):
    """True when a Python file declares NOTHING -- no definition, no import, no assignment.

    A docstring alone still counts as empty: a package that describes itself and contains no code
    is exactly the shape this looks for. Unparseable means UNKNOWN, so it is NOT called empty.
    """
    try:
        with open(abs_path, encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError, ValueError):
        return False                      # could not read it -> never claim it is empty
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            continue                      # a docstring is not content
        if isinstance(node, ast.Pass):
            continue
        return False
    return True


def _hollow_packages(nodes, root):
    """Directories that DECLARE a Python package and hold no code at all.

    ⛔ THE FAILURE: a subsystem is scaffolded -- the folder and its `__init__.py` are created, the
    work is never done, and from then on it reads as FINE in every report. Nothing is broken,
    nothing is missing, no import fails. The honest verdict is not "clean", it is UNKNOWN: the
    subsystem was declared and nobody can say whether its job is being done, because there is
    nothing there to do it.

    ⚠ KEPT NARROW ON PURPOSE, because a package that holds only an `__init__.py` is often
    perfectly legitimate. All three must hold before it is reported: the package declares itself
    with an `__init__.py`, that file declares nothing (a docstring does not count), and there is
    no other module or subpackage under it. A re-exporting `__init__.py`, a namespace package with
    submodules, and a test package are all left alone.
    """
    out = []
    pkgs = sorted(n for n in nodes if n.endswith("/__init__.py"))
    for init in pkgs:
        pkg = init[:-len("/__init__.py")]
        if pkg.startswith("tests/") or pkg == "tests" or "/tests/" in ("/" + pkg + "/"):
            continue
        if pkg.startswith("examples/") or "/examples/" in ("/" + pkg + "/"):
            continue
        others = [n for n in nodes
                  if n.startswith(pkg + "/") and n != init and n.endswith(".py")]
        if others:
            continue                      # it has modules or subpackages -- a real package
        if not _is_empty_module(os.path.join(root, init)):
            continue                      # its __init__ does the work -- also a real package
        out.append((pkg + "/", "declared as a subsystem and holds no code -- never built, or its "
                               "code lives somewhere else. UNKNOWN, not clean"))
    return out


def organize(root):
    """Build the tiered index. Reads only; moves nothing."""
    idx = Index()
    g = build_graph(root)
    idx.root = g.root
    idx.total = len(g.nodes)
    for n in sorted(g.nodes):
        deps = sorted(g.rev.get(n, ()))
        tier = _tier(n, is_imported=bool(deps))
        idx.tiers.setdefault(tier, []).append(n)
        # pinned = something depends on it (import) or names it by path (a graph edge target)
        referenced_by_path = any(tgt == n for _, tgt in g.dangling)  # (dangling never targets live)
        if deps or referenced_by_path:
            idx.pinned[n] = deps
        else:
            idx.movable.append(n)
        # a test file living outside any tests/ directory is misfiled by a rule nobody disputes
        base = os.path.basename(n)
        if base.startswith("test_") and base.endswith(".py") \
                and "/tests/" not in ("/" + n) and not n.startswith("tests/"):
            idx.misfiled.append((n, "a test file outside any tests/ directory"))
    idx.hollow = _hollow_packages(g.nodes, g.root)
    return idx
