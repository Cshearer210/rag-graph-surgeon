"""GRADE the shipped output against a rubric, and drive self-improvement.

A rubric is a list of (name, check(output_dir, context) -> (ok, detail)). The grader runs them and
returns a Report. The road uses a FAIL to re-run the build step with the specific failure appended
(self-improvement), then surfaces if it still fails after N tries.

The grader checks SHAPE mechanically and completely. Judging whether the output is *good* in a way
shape cannot capture is the pluggable model layer (agents.spot_check) applied to a sample -- not
required for the mechanical demo.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Report:
    checks: list = field(default_factory=list)      # (name, ok, detail)
    @property
    def passed(self):
        return sum(1 for _, ok, _ in self.checks if ok)
    @property
    def total(self):
        return len(self.checks)
    @property
    def score(self):
        return self.passed / self.total if self.total else 0.0
    @property
    def failures(self):
        return [(n, d) for n, ok, d in self.checks if not ok]
    def ok(self, threshold=1.0):
        return self.total > 0 and self.score >= threshold


def grade(output_dir: str, rubric: list, context: dict | None = None) -> Report:
    rep = Report()
    ctx = context or {}
    for name, check in rubric:
        try:
            ok, detail = check(output_dir, ctx)
        except Exception as e:                       # a check that crashes is a FAIL, not a skip
            ok, detail = False, "check raised %s: %s" % (type(e).__name__, e)
        rep.checks.append((name, bool(ok), detail))
    return rep


def selftest() -> int:
    ok = fail = 0

    def chk(name, cond):
        nonlocal ok, fail
        print("  %-52s %s" % (name[:52], "PASS" if cond else "FAIL"))
        ok, fail = ok + bool(cond), fail + (not cond)

    rubric = [
        ("always-true", lambda d, c: (True, "fine")),
        ("reads-context", lambda d, c: (c.get("v") == 1, "v=%s" % c.get("v"))),
        ("crasher", lambda d, c: 1 / 0),
    ]
    rep = grade("/tmp", rubric, {"v": 1})
    chk("counts passes", rep.passed == 2)
    chk("a crashing check is a FAIL not a skip", any(n == "crasher" for n, d in rep.failures))
    chk("score is passed/total", abs(rep.score - 2 / 3) < 1e-6)
    chk("ok(1.0) False when a check failed", rep.ok(1.0) is False)
    chk("ok(0.6) True at 0.66", rep.ok(0.6) is True)
    print("\n  %d passed, %d failed" % (ok, fail))
    return 1 if fail else 0


if __name__ == "__main__":
    import sys
    sys.exit(selftest())
