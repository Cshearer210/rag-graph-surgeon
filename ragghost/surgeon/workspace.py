"""WORKSPACE -- build an isolated place to work so the fix never touches the owner's original, copy
in only what the scope needs, and TRIAGE rules: keep the ones that help, flag the ones that hurt,
add the ones that are missing.

Isolation is the safety story: every fix in fix.py runs against the workspace copy. The original is
read, never written. Rule triage is a PROPOSAL for the owner -- a rule the tool wants removed is
flagged, never deleted.
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field

from . import index as index_mod

RULE_HINTS = ("rules", "rule", "canon", "standard", "spec", "claude.md", "agents.md")


@dataclass
class RuleTriage:
    keep: list = field(default_factory=list)     # rules that help this scope -> carried in
    flag: list = field(default_factory=list)     # rules that hurt -> (rel, why); owner approves removal
    add: list = field(default_factory=list)      # rules missing -> (name, why); tool proposes


@dataclass
class Workspace:
    path: str
    copied: list = field(default_factory=list)
    rules: RuleTriage = field(default_factory=RuleTriage)


def _is_rule(rel: str) -> bool:
    low = rel.lower()
    return any(h in low for h in RULE_HINTS)


def build(target: str, scope, dest: str, index=None) -> Workspace:
    """Copy the target into an isolated workspace (junk excluded), then triage its rules."""
    target = os.path.abspath(target)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)
    idx = index or index_mod.build(target)
    ws = Workspace(path=dest)
    for rel in idx.files:
        src = os.path.join(target, rel)
        dst = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try:
            shutil.copy2(src, dst)
            ws.copied.append(rel)
        except OSError:
            pass
    ws.rules = _triage_rules(dest, scope, idx)
    return ws


def _triage_rules(dest: str, scope, idx) -> RuleTriage:
    """KEEP a rule that mentions the chosen output or a general good practice; FLAG one that pins the
    system to a different output than the owner asked for; ADD the essentials a shipped output needs.
    Deterministic and conservative -- FLAG/ADD are proposals, never applied."""
    t = RuleTriage()
    output = scope.output
    other_outputs = {o for o in ("api", "dashboard", "landing", "cli") if o != output}
    for rel in idx.files:
        if not _is_rule(rel):
            continue
        try:
            text = open(os.path.join(dest, rel), encoding="utf-8", errors="replace").read().lower()
        except OSError:
            continue
        mentions_other = any(("only %s" % o) in text or ("must be a %s" % o) in text for o in other_outputs)
        if mentions_other and output not in text:
            t.flag.append((rel, "pins the system to a different output than '%s'" % output))
        else:
            t.keep.append(rel)
    # essentials every shipped output should have a rule for, if none present
    have = " ".join(open(os.path.join(dest, r), encoding="utf-8", errors="replace").read().lower()
                    for r in t.keep) if t.keep else ""
    for essential, why in (("a grading bar before ship", "grade"),
                           ("no secret in a committed file", "secret")):
        if why not in have:
            t.add.append((essential, "no rule enforces this yet, and a shipped output needs it"))
    return t


def write_manifest(ws: Workspace, scope) -> str:
    """A record the owner can read: what came in, what rules were kept/flagged/added."""
    man = {
        "workspace": ws.path,
        "files_copied": len(ws.copied),
        "output_requested": scope.output,
        "rules_kept": ws.rules.keep,
        "rules_flagged_for_owner": [{"file": r, "why": w} for r, w in ws.rules.flag],
        "rules_proposed_to_add": [{"rule": r, "why": w} for r, w in ws.rules.add],
    }
    p = os.path.join(ws.path, "_surgeon_workspace.json")
    json.dump(man, open(p, "w", encoding="utf-8"), indent=2)
    return p


def selftest() -> int:
    import tempfile
    ok = fail = 0

    def chk(name, cond):
        nonlocal ok, fail
        print("  %-54s %s" % (name[:54], "PASS" if cond else "FAIL"))
        ok, fail = ok + bool(cond), fail + (not cond)

    from .interview import Scope
    src = tempfile.mkdtemp()
    open(os.path.join(src, "products.json"), "w").write("[]")
    os.makedirs(os.path.join(src, "rules"))
    open(os.path.join(src, "rules", "good.md"), "w").write("Always grade before ship.")
    open(os.path.join(src, "rules", "reels.md"), "w").write("Output must be a dashboard only.")
    open(os.path.join(src, "node_modules_x"), "w").write("junk")   # not in a skip dir, still copied
    dest = os.path.join(tempfile.mkdtemp(), "ws")
    ws = build(src, Scope(output="landing"), dest)

    chk("workspace created and isolated from source", os.path.isdir(dest) and dest != src)
    chk("files copied in", any("products.json" in c for c in ws.copied))
    chk("fixing the copy never touches the source",
        (lambda: (open(os.path.join(dest, "products.json"), "w").write("CHANGED"),
                  open(os.path.join(src, "products.json")).read() == "[]")[1])())
    chk("helpful rule KEPT", any("good.md" in r for r in ws.rules.keep))
    chk("conflicting rule FLAGGED (not deleted)",
        any("reels.md" in r for r, _ in ws.rules.flag) and os.path.exists(os.path.join(dest, "rules", "reels.md")))
    chk("missing essential rule PROPOSED", any("secret" in name.lower() for name, _ in ws.rules.add))
    man = write_manifest(ws, Scope(output="landing"))
    chk("manifest written", os.path.exists(man))
    print("\n  %d passed, %d failed" % (ok, fail))
    return 1 if fail else 0


if __name__ == "__main__":
    import sys
    sys.exit(selftest())
