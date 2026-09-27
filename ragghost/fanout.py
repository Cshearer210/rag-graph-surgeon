# CALLED BY: whoever is about to spread work across workers; tested by
#            tests/test_ranks_meaning_and_fanout.py. Not a stage -- it takes no path.
# FIRES WHEN: asked, before a fan-out is started.
"""Should this work be spread across agents at all?

The expensive answer is not "no". It is "yes, silently, for a job one context could have done" --
which produces a report, consumes a fortune, and looks like diligence.

MEASURED, on a real run this is built from: 86 agents, 17.0M tokens, 4.1 hours, 26 findings
raised, 3 confirmed. 5.7M tokens per confirmed finding. Reading the same material in ONE context
would have found the same three for under a fiftieth of that.

    >>> from ragghost import fanout
    >>> fanout.decide(population=400, fits_one_context=False, judged_independently=True)
    Decision(verdict='FAN_OUT', ...)

⚠ THIS IS NOT `analyse.should_fan_out`, AND THE DIFFERENCE IS THE WHOLE REASON BOTH EXIST. Stage 7
answers the question about A CODEBASE, measured from its real dependency graph: do THESE subsystems
divide. This answers it about A JOB YOU ARE ABOUT TO RUN, from what the caller can state: does THIS
WORK divide. Neither can answer the other's question -- stage 7 cannot know what job you have in
mind, and this has no graph to measure -- so they are two answers to two questions rather than a
duplicate. What they may never be is two things under one name, which is why this module is
`fanout` and not `should_fan_out`.

THE RULE IT ENCODES, and it is the one people get wrong:

  "IT WOULD BE FASTER IN PARALLEL" IS NOT A REASON. The question is whether the work DIVIDES INTO
  INDEPENDENT JUDGEMENTS -- never whether it is large or slow. Synthesis does not divide: agents
  cannot see each other, so a merge is attempted N times and still has to be done once at the end.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Decision:
    verdict: str                     # FAN_OUT | ONE_CONTEXT | CANNOT_TELL
    why: str
    cap: int | None = None
    shape: str | None = None

    def __str__(self) -> str:
        s = "%s — %s" % (self.verdict, self.why)
        if self.cap:
            s += "\n  CAP the spread at %d and LOG what was dropped: silent truncation reads as " \
                 "'covered everything'." % self.cap
        if self.shape:
            s += "\n  SHAPE: %s" % self.shape
        return s


#: shapes where fanning out genuinely wins, each because one context cannot produce it
DIVIDES = {
    "independent-judgements": "each item is judged ALONE; nothing depends on another's answer",
    "adversarial": "the point is that the reviewers CANNOT see each other -- one context would "
                   "anchor on its own first answer",
    "loop-until-dry": "nobody knows how many there are; keep going until K rounds find nothing new",
}


def decide(population=None, fits_one_context=None, judged_independently=None,
           is_synthesis=False, already_recorded=False, max_agents=12):
    """-> Decision. Refuses to guess: an unanswered input is CANNOT_TELL, never a yes.

    `judged_independently` is the load-bearing input and it is deliberately NOT inferred from a
    description. A caller who cannot say whether the items are judged alone has not finished
    thinking about the work, and a tool that guesses for them turns that into a bill.
    """
    if already_recorded:
        return Decision("ONE_CONTEXT",
                        "this path is already RECORDED -- replay it. A reasoning model solving a "
                        "solved problem is not a cost problem, it is a DRIFT problem: it may "
                        "solve it differently this time, and then there are two answers.")
    if is_synthesis:
        return Decision("ONE_CONTEXT",
                        "SYNTHESIS does not divide. Agents cannot see each other, so the merge is "
                        "attempted N times and still has to be done once at the end. Fleets FIND; "
                        "the session SYNTHESISES.")
    if judged_independently is None or fits_one_context is None:
        missing = [n for n, v in (("judged_independently", judged_independently),
                                  ("fits_one_context", fits_one_context)) if v is None]
        return Decision("CANNOT_TELL",
                        "cannot answer without %s. A tool that guesses this for you turns an "
                        "unfinished thought into a bill." % " and ".join(missing))
    if fits_one_context:
        return Decision("ONE_CONTEXT",
                        "it FITS ONE CONTEXT, so the fan-out overhead IS the entire cost. "
                        "'It would be faster in parallel' is not a reason -- the question is "
                        "whether the work divides, never whether it is large.")
    if not judged_independently:
        return Decision("ONE_CONTEXT",
                        "it does not fit one context, but the items are NOT judged independently "
                        "-- so splitting them produces N partial answers that still have to be "
                        "reconciled. Reduce the population or change the question instead.")
    cap = min(max_agents, population or max_agents)
    return Decision("FAN_OUT",
                    "the population does not fit one context AND each item is judged alone (%s)"
                    % DIVIDES["independent-judgements"],
                    cap=cap,
                    shape="pipeline, not a barrier -- a barrier loses everything behind it if the "
                          "run is stopped. Two stopped fleets lost 2.26M tokens for zero results.")
