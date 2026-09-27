"""Gates and the harness that runs them.

A GATE is a check with THREE outcomes, never two: PASS, FAIL, UNKNOWN. A check that cannot look
(missing input, crash, timeout) returns UNKNOWN and is NEVER counted as a pass -- the single most
expensive failure in a self-built system is a checker that says "clean" when it never ran.

The HARNESS runs a set of gates and returns a verdict per gate plus a roll-up. Nothing here calls
a model; a gate is a pure function of the world it inspects.
"""
from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Callable

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"


@dataclass
class Verdict:
    gate: str
    outcome: str                      # PASS | FAIL | UNKNOWN
    detail: str = ""
    evidence: list = field(default_factory=list)   # concrete items, never a bare count
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.outcome == PASS

    def __str__(self) -> str:
        mark = {"PASS": "ok ", "FAIL": "XX ", "UNKNOWN": "?? "}[self.outcome]
        n = (" [%d]" % len(self.evidence)) if self.evidence else ""
        return "%s%-34s %s%s" % (mark, self.gate, self.detail[:80], n)


class Gate:
    """Wrap a function `fn(target) -> (outcome, detail, evidence)` so a crash becomes UNKNOWN,
    not a false PASS."""

    def __init__(self, name: str, fn: Callable, fixer: str | None = None):
        self.name = name
        self.fn = fn
        self.fixer = fixer            # name of the fix.py fixer that resolves a FAIL, if any

    def run(self, target) -> Verdict:
        t0 = time.time()
        try:
            outcome, detail, evidence = self.fn(target)
            if outcome not in (PASS, FAIL, UNKNOWN):
                outcome, detail = UNKNOWN, "gate returned a non-verdict: %r" % (outcome,)
            return Verdict(self.name, outcome, detail, list(evidence or []), time.time() - t0)
        except Exception as e:                       # a crash is UNKNOWN, never a pass
            return Verdict(self.name, UNKNOWN,
                           "gate raised %s: %s" % (type(e).__name__, e),
                           [traceback.format_exc().splitlines()[-1]], time.time() - t0)


class Harness:
    """Runs gates against a target and rolls up. Ordering is stable so a run is reproducible."""

    def __init__(self, gates: list[Gate]):
        self.gates = gates

    def run(self, target, only: set | None = None) -> list[Verdict]:
        return [g.run(target) for g in self.gates if not only or g.name in only]

    @staticmethod
    def rollup(verdicts: list[Verdict]) -> dict:
        return {
            "pass": sum(1 for v in verdicts if v.outcome == PASS),
            "fail": sum(1 for v in verdicts if v.outcome == FAIL),
            "unknown": sum(1 for v in verdicts if v.outcome == UNKNOWN),
            "total": len(verdicts),
            "fails": [v.gate for v in verdicts if v.outcome == FAIL],
            "unknowns": [v.gate for v in verdicts if v.outcome == UNKNOWN],
        }

    @staticmethod
    def clean(verdicts: list[Verdict]) -> bool:
        """Clean means every gate PASSED. A single UNKNOWN is not clean -- it is 'could not tell'."""
        return bool(verdicts) and all(v.outcome == PASS for v in verdicts)


def selftest() -> int:
    ok = fail = 0

    def chk(name, cond):
        nonlocal ok, fail
        print("  %-52s %s" % (name[:52], "PASS" if cond else "FAIL"))
        ok, fail = ok + bool(cond), fail + (not cond)

    good = Gate("always-pass", lambda t: (PASS, "fine", []))
    bad = Gate("always-fail", lambda t: (FAIL, "broken", ["thing-a"]))
    boom = Gate("crasher", lambda t: 1 / 0)
    liar = Gate("returns-garbage", lambda t: ("SORTOF", "x", []))

    vs = Harness([good, bad, boom, liar]).run(None)
    by = {v.gate: v for v in vs}
    chk("passing gate -> PASS", by["always-pass"].outcome == PASS)
    chk("failing gate -> FAIL with evidence", by["always-fail"].outcome == FAIL and by["always-fail"].evidence)
    chk("a CRASH becomes UNKNOWN, never a pass", by["crasher"].outcome == UNKNOWN)
    chk("a non-verdict return becomes UNKNOWN", by["returns-garbage"].outcome == UNKNOWN)
    roll = Harness.rollup(vs)
    chk("rollup counts 1/1/2", roll["pass"] == 1 and roll["fail"] == 1 and roll["unknown"] == 2)
    chk("clean() is False when any UNKNOWN present", Harness.clean(vs) is False)
    chk("clean() True only when all PASS", Harness.clean([good.run(None)]) is True)
    print("\n  %d passed, %d failed" % (ok, fail))
    return 1 if fail else 0


if __name__ == "__main__":
    import sys
    sys.exit(selftest())
