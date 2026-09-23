# CALLED BY: ragghost/__main__.py  (`python3 -m ragghost fix <path> [--apply]`)
# FIRES WHEN: asked -- a library module of a standalone tool, run by whoever downloaded it.
"""STAGE 8 -- FIX. Apply only what can be applied mechanically, and PROVE each fix with a check
that fires on its own.

⛔ THE FAILURE THIS STAGE EXISTS FOR: a "fix" that was never confirmed -- an edit made, called
done, and never re-measured, so nobody knows whether the defect actually went away. Every other
stage of this tool READS and never writes; this is the one that writes, so it is the one held to
the highest bar. It writes NOTHING unless asked (--apply), it touches ONLY the class of fix that
is deterministic and reversible, it REFUSES everything that needs a judgement, and after each
edit it RE-MEASURES the world: if the defect is not gone, it rolls the edit back and says so. A
proof is the world re-asked, never the edit re-described.

No dependencies, no network.
"""
from __future__ import annotations

import os
import shutil
import sys

from .organize import organize
from .plan import plan

__all__ = ["fix", "Fixes", "Fix"]


class Fix:
    def __init__(self, kind, target, mechanical, action):
        self.kind = kind
        self.target = target
        self.mechanical = mechanical      # can this tool apply it with no judgement?
        self.action = action              # what would happen / a human must do
        self.applied = False
        self.proven = None                # True/False after --apply; None in dry-run
        self.proof = ""                   # the check that fired, in words


class Fixes:
    def __init__(self):
        self.root = ""
        self.assessed = False
        self.applied_mode = False
        self.fixes = []

    def exit_code(self):
        if not self.assessed:
            return 2
        if self.applied_mode and any(f.proven is False for f in self.fixes):
            return 1                       # an applied fix did not prove out -- found something
        return 1 if self.fixes else 0

    def report(self, out=sys.stdout):
        w = out.write
        w("FIX  %s%s\n" % (self.root, "   [--apply]" if self.applied_mode else "   [dry run]"))
        w("=" * 70 + "\n")
        if not self.assessed:
            w("  NOTHING TO FIX. UNKNOWN, not clean.\n")
            return
        mech = [f for f in self.fixes if f.mechanical]
        judg = [f for f in self.fixes if not f.mechanical]
        if not self.fixes:
            w("  Nothing to fix. Every earlier stage came back clean.\n")
            return
        w("  %d mechanical fix(es), %d that need a human decision.\n\n" % (len(mech), len(judg)))
        if mech:
            w("  MECHANICAL -- deterministic and reversible:\n")
            for f in mech:
                if self.applied_mode:
                    mark = "OK  " if f.proven else "FAILED (rolled back)" if f.proven is False else "?"
                    w("    [%s] %s\n        %s\n        proof: %s\n" % (mark, f.target, f.action, f.proof))
                else:
                    w("    [would apply] %s\n        %s\n        will prove: %s\n"
                      % (f.target, f.action, f.proof))
        if judg:
            w("\n  NEEDS A HUMAN -- refused, with the check that would confirm your fix:\n")
            for f in judg:
                w("    [%-9s] %s\n        %s\n        confirm with: %s\n"
                  % (f.kind, f.target, f.action, f.proof))
        if not self.applied_mode and mech:
            w("\n  Nothing was written. Re-run with --apply to make the mechanical fixes.\n")


def _still_misfiled(root, relpath):
    """Re-ASK the world: does organize still flag this file? The proof, not the edit."""
    return any(f == relpath for f, _ in organize(root).misfiled)


def fix(root, apply=False):
    """Dry-run by default. --apply writes ONLY the mechanical class, and proves each edit."""
    f = Fixes()
    f.applied_mode = bool(apply)
    idx = organize(root)
    f.root = idx.root
    if not idx.total:
        return f
    f.assessed = True

    # ---- the mechanical class: a test file living outside tests/ -> move it into tests/ ----
    for rel, why in idx.misfiled:
        base = os.path.basename(rel)
        dest_rel = os.path.join("tests", base)
        src = os.path.join(root, rel)
        dest = os.path.join(root, dest_rel)
        if os.path.exists(dest):
            # a file already sits at the destination -> NOT mechanical, a human must decide
            item = Fix("misfiled", rel, False,
                       "a test file outside tests/, but tests/%s already exists -- merge by hand" % base)
            item.proof = "tests/%s is the only copy and %s no longer exists" % (base, rel)
            f.fixes.append(item)
            continue
        item = Fix("misfiled", rel, True, "move %s -> %s" % (rel, dest_rel))
        item.proof = "organize() no longer flags %s as misfiled" % rel
        if apply:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(src, dest)
            if _still_misfiled(root, rel) or not os.path.exists(dest):
                shutil.move(dest, src)                      # roll back -- the proof did not flip
                item.applied, item.proven = False, False
            else:
                item.applied, item.proven = True, True
        f.fixes.append(item)

    # ---- everything else the plan found: refused, but carries its proving check ----
    proofs = {
        "moved-ref": "graph() reports 0 dangling references",
        "orphan": "graph() reports 0 orphans (something imports it, or you deleted it on purpose)",
        "retrieval": "retrieve() audit passes -- present probe found, noise scores 0.0",
        "no-gate": "harness() reports 0 ungated subsystems",
        "scan": "scan() -- the two independent counts agree",
    }
    for sev, kind, target, action in plan(root).items:
        if kind == "misfiled":
            continue                                        # handled above, mechanically
        item = Fix(kind, target, False, action)
        item.proof = proofs.get(kind, "re-run the earlier stage and confirm it comes back clean")
        f.fixes.append(item)
    return f
