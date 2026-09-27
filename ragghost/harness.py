# CALLED BY: ragghost/__main__.py  (`python3 -m ragghost harness <path>`)
# FIRES WHEN: asked -- a library module of a standalone tool, run by whoever downloaded it.
"""STAGE 5 -- HARNESS. Split the system into subsystems, each with its doors and its gate.

⛔ THE FAILURE THIS STAGE EXISTS FOR: a subsystem that NOTHING checks. It runs, it is depended on,
and no test or gate guards it -- so when it breaks, nothing says so until something downstream
does, days later. A system with no boundaries is one big blast radius; a system split into
harnesses, each with a gate on its door, fails loudly and locally.

This stage groups the code into harnesses (one per top-level component), finds each harness's
DOORS (the files other harnesses reach into -- its real public surface, from the stage-2 graph),
and asks whether the harness has a GATE (a test that exercises it). A code harness with no gate is
the finding.

No dependencies, no network. It reads; it never writes to the target.
"""
from __future__ import annotations

import os
import sys

from .graph import build_graph

__all__ = ["harnesses", "Harnesses"]


def _component(path):
    """The harness a file belongs to: its top-level directory, or '(root)' for a top-level file.

    ⚠ `path` is a GRAPH NODE, which is an identifier, not a filename. `build_graph` normalises every
    node with `.replace(os.sep, "/")` at the one place it creates them (graph.py, the os.walk), so
    the separator here is forward slash on every platform by contract. Splitting on the platform
    separator instead would be the bug: on Windows every node would then be one part and the whole
    stage would collapse into a single `(root)` harness -- silently, with a clean exit code.
    """
    parts = path.split("/")  # path-id: ok -- a graph node, normalised where graph.py creates it
    return parts[0] if len(parts) > 1 else "(root)"


class Harnesses:
    def __init__(self):
        self.root = ""
        self.groups = {}          # harness -> {"files","code","doors","gated","tests"}
        self.ungated = []         # harnesses of code with no gate
        self.total_files = 0

    def exit_code(self):
        if not self.groups:
            return 2
        if self.ungated:
            return 1
        return 0

    def report(self, out=sys.stdout):
        w = out.write
        w("HARNESS  %s\n" % self.root)
        w("=" * 70 + "\n")
        if not self.groups:
            w("  NO HARNESSES. UNKNOWN, not clean -- nothing was grouped.\n")
            return
        w("  %d file(s) in %d harness(es)\n" % (self.total_files, len(self.groups)))
        w("\n  EACH HARNESS -- its size, its doors (public surface), and its gate\n")
        for name in sorted(self.groups):
            g = self.groups[name]
            gate = "gate: %s" % ("yes" if g["gated"] else "⛔ NONE")
            w("    %-24s %3d file(s)  %2d door(s)  %s\n"
              % (name[:24], len(g["files"]), len(g["doors"]), gate))
        if self.ungated:
            w("\n  ⛔ %d CODE HARNESS(ES) WITH NO GATE -- nothing tests these\n" % len(self.ungated))
            for name in self.ungated:
                w("    %s  (%d file(s))\n" % (name, len(self.groups[name]["files"])))
            w("\n  A subsystem no test guards fails silently. Add a gate before trusting it.\n")
        else:
            w("\n  Every code harness has a gate. Failures here would be caught locally.\n")


def harnesses(root):
    """Group the system into harnesses and find the ungated ones. Reads only."""
    h = Harnesses()
    g = build_graph(root)
    h.root = g.root
    h.total_files = len(g.nodes)
    for n in g.nodes:
        comp = _component(n)
        grp = h.groups.setdefault(comp, {"files": set(), "code": set(), "doors": set(),
                                          "gated": False, "tests": set()})
        grp["files"].add(n)
        base = os.path.basename(n)
        is_test = base.startswith("test_") or "/tests/" in n or n.startswith("tests/")
        if is_test:
            grp["tests"].add(n)
        elif n.endswith(".py"):
            grp["code"].add(n)
    # doors: a file reached by an edge from OUTSIDE its own harness
    for src, targets in g.edges.items():
        for tgt in targets:
            if _component(src) != _component(tgt):
                h.groups[_component(tgt)]["doors"].add(tgt)
    # a harness is gated if it has its own tests, OR a test anywhere imports one of its files
    tested_files = set()
    for src, targets in g.edges.items():
        base = os.path.basename(src)
        if base.startswith("test_") or "/tests/" in src or src.startswith("tests/"):
            tested_files |= targets
    for name, grp in h.groups.items():
        grp["gated"] = bool(grp["tests"]) or bool(grp["code"] & tested_files)
        if grp["code"] and not grp["gated"]:
            h.ungated.append(name)
    h.ungated.sort()
    return h
