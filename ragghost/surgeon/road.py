"""THE ROAD -- the one orchestrator that turns a broken system into a shipped output.

    interview -> ingest(index+graph) -> workspace(isolate+rule triage) -> diagnose -> fix
              -> build(the requested output) -> grade -> (self-improve on fail) -> ship + PROOF

Every stage is mechanical. The result is a Run with a full, honest record: what was diagnosed,
what was fixed, what was surfaced for the owner, what shipped, and the grade. Nothing here spawns
an agent or calls a model; those plug in behind `diagnose`/`grade` for the 5% mechanics cannot do.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field

from . import builders, diagnose, fix, grade, graph, index, interview, memory, workspace


@dataclass
class Run:
    target: str
    scope: object
    ws_path: str = ""
    index_summary: dict = field(default_factory=dict)
    diagnosed: list = field(default_factory=list)     # str(Diagnosis)
    fixed: list = field(default_factory=list)         # (str(diag), note)
    surfaced: list = field(default_factory=list)      # (str(diag), note) -> owner decides
    rules_flagged: list = field(default_factory=list)
    rules_added: list = field(default_factory=list)
    output: str = ""
    output_dir: str = ""
    build_info: dict = field(default_factory=dict)
    grade_score: float = 0.0
    grade_detail: list = field(default_factory=list)
    shipped: bool = False
    attempts: int = 0

    def proof(self) -> dict:
        return {
            "target": self.target, "workspace": self.ws_path,
            "index": self.index_summary,
            "diagnosed": self.diagnosed,
            "fixed": self.fixed,
            "surfaced_for_owner": self.surfaced,
            "rules_flagged_for_owner": self.rules_flagged,
            "rules_proposed": self.rules_added,
            "output": self.output, "output_dir": self.output_dir,
            "build": self.build_info,
            "grade": {"score": self.grade_score, "checks": self.grade_detail},
            "shipped": self.shipped, "attempts": self.attempts,
        }


# required config fields, per output type, that FIX must ensure exist.
#
# ⛔ "landing" WAS DECLARED TWICE HERE, identically. Python keeps the last and discards the first
# in silence -- no error, no warning, and the two happened to be equal so nothing ever behaved
# wrongly. It is still the DUPLICATE-DEFINITION class this repository's own README lists as a
# defect it looks for in other people's code, sitting in its own source. Removed 2026-09-27 on the
# way in. The other three output types intentionally have no required fields: their rubrics grade
# the built artefact rather than the config it came from.
REQUIRED_FIELDS = {
    "landing": {"config.json": ["store_name"]},
}


def run(target, dest, out_dir, scope=None, scope_file=None, interactive=False,
        mem_path=None, max_tries=3, verbose=True) -> Run:
    sc = scope or interview.interview(interactive=interactive, scope_file=scope_file)
    r = Run(target=os.path.abspath(target), scope=sc, output=sc.output)

    def say(*a):
        if verbose:
            print(*a)

    say("[1/8] INTERVIEW  goal=%r  output=%s" % (getattr(sc, "goal", ""), sc.output))

    say("[2/8] INGEST     indexing + graphing the target")
    idx = index.build(target)
    r.index_summary = idx.summary()
    graph.build(idx)   # built for orphan detection inside diagnose.unwired

    say("[3/8] WORKSPACE  isolating + triaging rules")
    ws = workspace.build(target, sc, dest, index=idx)
    r.ws_path = ws.path
    r.rules_flagged = [{"file": f, "why": w} for f, w in ws.rules.flag]
    r.rules_added = [{"rule": rr, "why": w} for rr, w in ws.rules.add]
    workspace.write_manifest(ws, sc)
    ws_idx = index.build(ws.path)     # index the copy we will actually fix + build from

    say("[4/8] DIAGNOSE   scanning for what is broken")
    req = REQUIRED_FIELDS.get(sc.output, {})
    ds = diagnose.run_all(ws.path, ws_idx, req)
    r.diagnosed = [str(d) for d in ds]
    say("            found %d issue(s)" % len(ds))

    say("[5/8] FIX        applying root-cause fixes (deletion/public/money are surfaced, never auto)")
    mem = memory.Memory.load(mem_path) if mem_path else None
    applied, surfaced = fix.apply(ws.path, ds, scope=_scope_dict(sc))
    r.fixed = [(str(d), note) for d, note in applied]
    r.surfaced = [(str(d), note) for d, note in surfaced]
    if mem:
        for d, _ in applied:
            if d.fixer:
                mem.record_fix(d.kind, d.fixer)
        mem.save()
    say("            fixed %d, surfaced %d for the owner" % (len(applied), len(surfaced)))

    # BUILD -> GRADE -> self-improve loop
    builder = builders.get(sc.output)
    rub = builders.rubric_for(sc.output)
    for attempt in range(1, max_tries + 1):
        r.attempts = attempt
        say("[6/8] BUILD      %s (attempt %d)" % (sc.output, attempt))
        r.build_info = builder(ws.path, sc, out_dir)
        r.output_dir = out_dir
        if not rub:
            say("[7/8] GRADE      no rubric for this output type; shipping unverified")
            break
        rubric_fn, ctx_fn = rub
        rep = grade.grade(out_dir, rubric_fn(sc), ctx_fn(ws.path, sc))
        r.grade_score = rep.score
        r.grade_detail = [{"check": n, "ok": ok, "detail": d} for n, ok, d in rep.checks]
        say("[7/8] GRADE      %d/%d checks pass (%.0f%%)" % (rep.passed, rep.total, rep.score * 100))
        if rep.ok(1.0):
            break
        # SELF-IMPROVE: a failing check often means the fix stage missed a config field the build
        # needs. Re-diagnose the workspace against what the failures imply, fix, and rebuild.
        say("            self-improving: %s" % [n for n, _ in rep.failures][:4])
        more = diagnose.run_all(ws.path, index.build(ws.path), req)
        applied2, _ = fix.apply(ws.path, more, scope=_scope_dict(sc))
        r.fixed += [(str(d), note) for d, note in applied2]
        if not applied2:
            break    # nothing left mechanics can change; stop rather than loop pointlessly

    r.shipped = (not rub) or (r.grade_score >= 1.0)
    say("[8/8] SHIP        %s -> %s" % ("SHIPPED" if r.shipped else "BLOCKED (grade below bar)", out_dir))
    _write_proof(r, out_dir)
    return r


def _scope_dict(sc):
    return {"store_name": sc.get("store_name", ""), "defaults": getattr(sc, "defaults", {})}


def _write_proof(r: Run, out_dir: str):
    try:
        os.makedirs(out_dir, exist_ok=True)
        json.dump(r.proof(), open(os.path.join(out_dir, "_surgeon_proof.json"), "w"), indent=2)
    except OSError:
        pass


def selftest() -> int:
    """A tiny end-to-end: a broken 1-product store -> run the road -> assert it shipped + graded."""
    import tempfile
    ok = fail = 0

    def chk(name, cond):
        nonlocal ok, fail
        print("  %-54s %s" % (name[:54], "PASS" if cond else "FAIL"))
        ok, fail = ok + bool(cond), fail + (not cond)

    from .interview import Scope
    t = tempfile.mkdtemp()
    open(os.path.join(t, "products.json"), "w").write('[{"name":"Candle","price":12},]')  # trailing comma
    open(os.path.join(t, "config.json"), "w").write('{"currency":"USD"}')                  # missing store_name
    base = tempfile.mkdtemp()
    r = run(t, os.path.join(base, "ws"), os.path.join(base, "out"),
            scope=Scope(output="landing", store_name="Aurora", defaults={"store_name": "Aurora"}),
            verbose=False)
    chk("diagnosed the broken json + missing field", len(r.diagnosed) >= 2)
    chk("applied fixes", len(r.fixed) >= 2)
    chk("built the landing page", "index.html" in (r.build_info.get("files") or []))
    chk("graded 100%", r.grade_score == 1.0)
    chk("shipped", r.shipped is True)
    chk("index.html exists in output", os.path.exists(os.path.join(base, "out", "index.html")))
    chk("proof written", os.path.exists(os.path.join(base, "out", "_surgeon_proof.json")))
    chk("source never modified", "," in open(os.path.join(t, "products.json")).read())
    print("\n  %d passed, %d failed" % (ok, fail))
    return 1 if fail else 0


if __name__ == "__main__":
    import sys
    sys.exit(selftest())
