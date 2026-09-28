# CALLED BY: ragghost/__main__.py  (`python3 -m ragghost plan <path>`)
# FIRES WHEN: asked -- a library module of a standalone tool, run by whoever downloaded it.
"""STAGE 6 -- PLAN. A ranked list of what to do, derived from the real state, never typed.

⛔ THE FAILURE THIS STAGE EXISTS FOR: a plan written from memory or aspiration lists what someone
THOUGHT was wrong, in the order they happened to think of it. This plan is generated from the
findings of stages 1-5 -- every item points at a real thing the earlier stages measured -- and it
is ranked by HARM, not by the order found, so the thing most likely to be silently costing you
sits at the top.

No dependencies, no network. It reads; it never writes to the target.
"""
from __future__ import annotations

import sys

from .scan import scan
from .graph import build_graph
from .organize import organize
from .harness import harnesses
from .retrieve import build_index

__all__ = ["plan", "Plan"]

# harm rank: lower number = worse. A silent breakage outranks an untidy layout.
SEV = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


class Plan:
    def __init__(self):
        self.root = ""
        self.items = []          # (severity, kind, target, action)
        self.assessed = False    # False => could not assess (empty/unknown), never "clean"

    def exit_code(self):
        if not self.assessed:
            return 2
        return 1 if self.items else 0

    def report(self, out=sys.stdout):
        w = out.write
        w("PLAN  %s\n" % self.root)
        w("=" * 70 + "\n")
        if not self.assessed:
            w("  COULD NOT ASSESS. UNKNOWN, not clean -- the scan found nothing to plan over.\n")
            return
        if not self.items:
            w("  Nothing to do. Every earlier stage came back clean.\n")
            return
        w("  %d action(s), ranked by harm (worst first). Each points at a real finding.\n"
          % len(self.items))
        cur = None
        for sev, kind, target, action in self.items:
            if sev != cur:
                w("\n  %s\n" % sev)
                cur = sev
            w("    [%-8s] %s\n" % (kind, action))
            w("               -> %s\n" % target)


def plan(root):
    """Compose stages 1-5 into one harm-ranked plan. Reads only."""
    p = Plan()
    s = scan(root)
    p.root = s.root
    if not s.files:
        return p                      # assessed stays False -> exit 2
    p.assessed = True

    if s.agrees is False:
        p.items.append(("CRITICAL", "scan", "walk=%d vs independent=%d" % (s.files, s.independent),
                        "the two file counts disagree -- one method is blind; resolve before trusting any scan"))

    g = build_graph(root)
    for f, tgt in g.dangling:
        p.items.append(("CRITICAL", "moved-ref", "%s names %s (missing)" % (f, tgt),
                        "a named path resolves to nothing -- update the reference or restore the file"))
    for n in g.orphans:
        p.items.append(("MEDIUM", "orphan", n,
                        "nothing depends on this file -- wire it in, or delete it if it is dead"))
    for name, _kind, files, method in g.duplicates:
        # HIGH, not CRITICAL: nothing is broken at this instant. It outranks an orphan because a
        # stale second copy is found by whoever hits the bug that was already fixed -- later, and
        # more expensively, than finding a file nobody calls.
        p.items.append(("HIGH", "duplicate", "%s() in %s" % (name, ", ".join(files)),
                        "one job defined in %d places (%s) -- fix one and the rest stay stale; "
                        "keep one definition and have the others call it" % (len(files), method)))

    r = build_index(root)
    if r.audit_present is not None and not r.audit_present[2]:
        p.items.append(("CRITICAL", "retrieval", "present probe %r not found" % r.audit_present[0],
                        "the retriever cannot find a term it indexed -- it reports a full system as empty"))
    if r.audit_noise and r.audit_noise[1] > 0.0:
        p.items.append(("CRITICAL", "retrieval", "noise scored %.3f" % r.audit_noise[1],
                        "the retriever ranks gibberish above zero -- its answers are untrustworthy"))

    h = harnesses(root)
    for name in h.ungated:
        p.items.append(("HIGH", "no-gate", "harness %r (%d files)" % (name, len(h.groups[name]["files"])),
                        "a code subsystem no test guards -- add a gate before trusting it"))

    idx = organize(root)
    for f, why in idx.misfiled:
        p.items.append(("LOW", "misfiled", "%s (%s)" % (f, why),
                        "move it to where its kind belongs -- low risk, nothing references it"))

    p.items.sort(key=lambda it: SEV.get(it[0], 9))
    return p
