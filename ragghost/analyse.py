# CALLED BY: ragghost/__main__.py  (`python3 -m ragghost analyse <path>`)
# FIRES WHEN: asked -- a library module of a standalone tool, run by whoever downloaded it.
"""STAGE 7 -- ANALYSE. Decide whether the work divides into independent parts, and REFUSE the
fan-out when it does not.

⛔ THE FAILURE THIS STAGE EXISTS FOR: reaching for a fleet of parallel workers when one pass would
have done the job. Parallelism has a fixed per-worker cost; it only pays when the work splits into
units that can each be judged ALONE. When the units depend on each other, N parallel judges each
see a fragment, none sees the whole, and the merge has to be done once anyway -- so the fan-out
was pure overhead. This stage makes that decision explicitly, from the real dependency structure,
and refuses the fan-out where the work does not actually divide.

⚠ THE SIBLING QUESTION LIVES IN `ragghost/fanout.py` AND IS NOT THIS ONE. This stage asks it about
A CODEBASE and answers from the measured dependency graph. `fanout.decide()` asks it about A JOB
somebody is about to run and answers from what the caller can state -- including CANNOT_TELL when
they cannot, because a tool that guesses that for you turns an unfinished thought into a bill.
Two questions, two answers, one name each.

No dependencies, no network. It reads; it never writes to the target.
"""
from __future__ import annotations

import sys

from .graph import build_graph
from .harness import harnesses

__all__ = ["should_fan_out", "analyse", "Analysis"]

MIN_UNITS = 8            # below this, the per-worker overhead exceeds the work itself


def should_fan_out(n_units, n_cross_edges, min_units=MIN_UNITS):
    """The core decision, pure and testable. Returns (fan_out: bool, reason: str).

    Fan out only when there are ENOUGH units AND they are INDEPENDENT. Either too few, or any
    cross-dependency between them, means one pass -- the second because dependent units cannot be
    judged alone without each worker missing what it depends on.
    """
    if n_units <= 0:
        return (False, "no units to analyse")
    if n_units < min_units:
        return (False, "only %d unit(s); the per-worker overhead would exceed the work -- one pass"
                % n_units)
    if n_cross_edges > 0:
        return (False, "%d unit(s) but %d cross-dependency edge(s) between them; they do not "
                "divide cleanly -- one pass, or parallel workers each miss what they depend on"
                % (n_units, n_cross_edges))
    return (True, "%d independent unit(s), no cross-dependencies -- this divides cleanly" % n_units)


class Analysis:
    def __init__(self):
        self.root = ""
        self.n_units = 0
        self.n_cross_edges = 0
        self.fan_out = False
        self.reason = ""
        self.assessed = False

    def exit_code(self):
        if not self.assessed:
            return 2
        return 1 if self.fan_out else 0    # 1 = real divisible parallel work exists; 0 = one pass

    def report(self, out=sys.stdout):
        w = out.write
        w("ANALYSE  %s\n" % self.root)
        w("=" * 70 + "\n")
        if not self.assessed:
            w("  NOTHING TO ANALYSE. UNKNOWN, not clean.\n")
            return
        w("  %d subsystem(s), %d cross-dependency edge(s) between them\n"
          % (self.n_units, self.n_cross_edges))
        verdict = "FAN OUT" if self.fan_out else "ONE PASS"
        w("\n  DECISION: %s\n    %s\n" % (verdict, self.reason))
        if not self.fan_out:
            w("\n  Refusing a fan-out here would save its entire cost. The work is handled in one\n"
              "  pass, in dependency order.\n")


def analyse(root):
    """Decide fan-out vs one-pass for THIS system's subsystems. Reads only."""
    a = Analysis()
    g = build_graph(root)
    a.root = g.root
    if not g.nodes:
        return a
    a.assessed = True
    h = harnesses(root)
    # units = code harnesses; cross-edges = graph edges linking two different harnesses
    from .harness import _component
    code_harnesses = {name for name, grp in h.groups.items() if grp["code"]}
    a.n_units = len(code_harnesses)
    cross = 0
    for src, targets in g.edges.items():
        for tgt in targets:
            if _component(src) in code_harnesses and _component(tgt) in code_harnesses \
                    and _component(src) != _component(tgt):
                cross += 1
    a.n_cross_edges = cross
    a.fan_out, a.reason = should_fan_out(a.n_units, a.n_cross_edges)
    return a
