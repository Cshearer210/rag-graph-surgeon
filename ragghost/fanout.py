# CALLED BY: whoever is about to spread work across workers; examples/should_i_fan_out.py;
#            tested by tests/test_fanout.py and tests/test_hostile.py.
# FIRES WHEN: asked, before a fan-out is started. Not a stage -- it takes no path.
"""Should you spread this work across agents at all?

    Does this work DIVIDE INTO INDEPENDENT JUDGEMENTS -- or am I about to pay N times a fixed
    overhead for something one context would do once, better?

⭐ ANCHORED ON A REAL POST-MORTEM: 86 agents, 17.0 million tokens, 1,175 tool calls, 4.1 hours, and
3 confirmed findings out of 26 raised. **5.7M tokens per confirmed finding**, for an answer a single
context would have reached for a fiftieth of it. Nobody publishes their own 17M-token post-mortem,
which is exactly why it is worth publishing.

⛔ "IT WOULD BE FASTER IN PARALLEL" IS NOT A REASON, and it is the reason almost always given. The
question is never whether the work is large or slow. It is whether the pieces can be judged WITHOUT
SEEING EACH OTHER. Four shapes genuinely can; everything else is one context's job.

THE FOUR THAT WIN, each earned rather than theorised:
    TOO BIG FOR ONE CONTEXT   a population where each item is judged on its own
    INDEPENDENT OPINIONS      the POINT is that they cannot see each other -- an adversarial verify,
                              a blind panel. One context anchors on its own first answer
    LOOP UNTIL DRY            nobody knows how many there are; keep going until K rounds turn up
                              nothing new. A single pass returns "what I noticed", never "all"
    BREADTH ONE CONTEXT CANNOT HOLD   the same transform across many places at once

AND THE ONE THAT ALWAYS LOSES, measured twice:
    SYNTHESIS                 agents cannot see each other, so the merge is attempted N times and
                              still has to be done once at the end. Fleets FIND; the caller
                              SYNTHESISES.

⚠ THIS IS NOT `analyse.should_fan_out`, and the difference is why both exist. Stage 7 asks this
about A CODEBASE and answers from its measured dependency graph: do THESE subsystems divide.
This asks it about A JOB somebody is about to run and answers from the shape they name. Neither can
answer the other's question -- stage 7 cannot know what job you have in mind, and this has no graph
to measure. Two answers to two questions; what they may never be is two things under one name.

⛔ THIS FILE IS A MERGE AND THE VERSION THAT SHIPPED FIRST LOST. A weaker 120-line version was
published on 2026-09-27 before anyone noticed a 139-line one existed in unpublished work. The
survivor takes named SHAPES over a row of booleans (nine of them, and an unrecognised one is CANNOT
TELL rather than a yes), a `code` that is already this tool's 0/1/2, the cap-of-zero case, and the
one-item case. What it keeps from the loser is the measured cost of a barrier, below.
"""
from __future__ import annotations

__all__ = ["Shape", "SHAPES", "advise", "Advice"]


class Shape(object):
    """One shape of work, and whether fanning it out is honest."""

    def __init__(self, key, divides, why):
        self.key = key
        self.divides = divides
        self.why = why


SHAPES = [
    Shape("population", True,
          "each item is judged on its own and the population does not fit one context"),
    Shape("independent-opinions", True,
          "the point is that the judges cannot see each other; one context would anchor on its "
          "own first answer"),
    Shape("loop-until-dry", True,
          "nobody knows how many there are, so it runs until rounds stop finding anything new"),
    Shape("breadth", True,
          "the same transform across more places than one context can hold at once"),
    Shape("synthesis", False,
          "agents cannot see each other, so the merge is attempted N times and still has to be "
          "done once at the end -- fleets FIND, the caller SYNTHESISES"),
    Shape("known-path", False,
          "the path is already recorded, so replaying it mechanically is cheaper and cannot "
          "drift. A reasoning model re-solving a solved problem is not a cost problem, it is a "
          "DRIFT problem: it may solve it differently, and then there are two answers"),
    Shape("same-or-not", False,
          "'is this the same as that' is a similarity question -- the smallest embedding model "
          "answers it for nothing"),
    Shape("already-answered", False,
          "a store already holds this answer; asking agents re-derives what is on disk"),
    Shape("fits-one-context", False,
          "it fits in one context, so the fan-out overhead IS the entire cost"),
]
_BY_KEY = {s.key: s for s in SHAPES}


class Advice(object):
    """0 fan out · 1 do NOT fan out · 2 cannot tell."""

    def __init__(self, code, headline, detail="", numbers=None):
        self.code = int(code)
        self.headline = headline
        self.detail = detail
        self.numbers = numbers or {}

    def __repr__(self):
        return "Advice(code=%d, %r)" % (self.code, self.headline)

    def __str__(self):
        s = "%s %s" % (("FAN OUT", "DO NOT FAN OUT", "CANNOT TELL")[self.code], self.headline)
        if self.numbers:
            s += "\n  " + "  ".join("%s=%s" % (k, v) for k, v in sorted(self.numbers.items()))
        if self.detail:
            s += "\n  " + self.detail
        return s

    def exit_code(self):
        """So a caller can `raise SystemExit(a.exit_code())` like every other part of this tool."""
        return self.code


#: Kept from the version that lost the merge, because it is a measurement and not an opinion: two
#: stopped fleets lost 2.26M tokens for ZERO results, because every finding sat behind one barrier.
_BARRIER = ("Prefer a pipeline over a barrier -- a barrier loses every result if the run is "
            "stopped, and two stopped fleets lost 2.26M tokens for zero results that way.")


def advise(shape, items=None, fits_one_context=None, cap=None):
    """Should this be fanned out? -> Advice.

    ⛔ AN UNRECOGNISED SHAPE IS CANNOT TELL, NEVER A YES. The permissive answer here spends real
    money and hours, so an unknown shape must never fall through to "sure, go ahead" -- that is the
    same class as a checker reporting clean because it could not look.
    """
    s = _BY_KEY.get(str(shape or "").strip().lower())
    if s is None:
        return Advice(2, "unrecognised shape %r" % shape,
                      "Name the shape of the work before dispatching anything. Known shapes: "
                      + ", ".join(sorted(_BY_KEY)),
                      {"known_shapes": len(_BY_KEY)})
    nums = {"shape": s.key}
    if items is not None:
        nums["items"] = items
    if not s.divides:
        return Advice(1, "this shape does not divide into independent judgements", s.why, nums)
    # It divides -- but a divisible shape that FITS one context is still not worth the overhead.
    if fits_one_context:
        return Advice(1, "it divides, but it fits in one context",
                      "The fan-out overhead is then the entire cost. Dividing is necessary for "
                      "fanning out and is not on its own a reason to.", nums)
    if items is not None and items <= 1:
        return Advice(1, "one item is not a population",
                      "Fanning out over a single item pays the whole per-agent overhead to do "
                      "what the caller could do directly.", nums)
    # ⛔ A CAP OF ZERO OR LESS MEANS NOTHING RUNS, AND SAYING "FAN OUT" TO THAT IS A CONFIDENT WRONG
    # ANSWER -- the exact shape this tool is built to find. Found by a hostile-input pass on
    # 2026-09-20, which had ENSHRINED the wrong behaviour in its own expectation before the
    # expectation was checked by hand. A battle test that agrees with the bug is worse than no
    # battle test, because it certifies it.
    if items is not None and cap is not None and cap <= 0:
        nums["dropped"] = items
        return Advice(1, "the cap is %d, so NOTHING would run" % cap,
                      "A fan-out that dispatches nothing is not a fan-out. Raise the cap or do "
                      "the work here.", nums)
    if items is not None and cap is not None and items > cap:
        nums["dropped"] = items - cap
        return Advice(0, "fan out, but %d item(s) will be DROPPED by the cap" % (items - cap),
                      "Silent truncation reads as 'covered everything'. Print what was dropped, "
                      "or raise the cap deliberately. " + _BARRIER, nums)
    return Advice(0, "fan out: " + s.why, _BARRIER, nums)
