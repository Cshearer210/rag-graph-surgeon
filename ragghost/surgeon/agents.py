"""The judgment layer -- sub-agents, semantic retrieval, and a fleet -- as PLUGGABLE interfaces
with mechanical defaults, so the surgeon runs $0 and offline out of the box and a real model plugs
in for the 5% mechanics cannot do.

Why interfaces and not hardcoded model calls: FABLE-REPO-PLAN's cost discipline. Most of the work
(lookup, walk, count, replay a known path) needs no model, and a fleet spent 5.7M tokens per
confirmed finding when a single read would have done. So the expensive model is a FUNCTION the road
calls only when a stage returns CANNOT_TELL, never a member of the pipeline.

Three plug points:
  SemanticIndex  -- "is this the same idea as that": the one question exactness cannot answer.
                    Default: a mechanical token-overlap ranker (no embeddings). Swap in a local
                    $0 embedding model or a hosted one by implementing .rank().
  Verifier       -- the ARBITER: judge a finding CONFIRMED / CONTRADICTED / NO-PRIMARY-SOURCE.
                    Default: mechanical (a finding with concrete evidence is CONFIRMED, else
                    surfaced). Swap in an adversarial model pass told the work is broken.
  Fleet          -- fan-out for a population too big for one context. Default: sequential map.
                    Swap in Claude Code's Workflow tool (pipeline/parallel, resume).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

CONFIRMED, CONTRADICTED, NO_SOURCE = "CONFIRMED", "CONTRADICTED", "NO-PRIMARY-SOURCE"
_WORD = re.compile(r"[a-z0-9]+")


class SemanticIndex:
    """Default: mechanical token-overlap similarity. Deterministic, offline, no model.
    Answers "which known item is this most like" well enough to route; a real embedding model
    plugs in by subclassing and overriding `score`."""

    def __init__(self, corpus: list[str]):
        self.corpus = corpus
        self._toks = [set(_WORD.findall(c.lower())) for c in corpus]

    def score(self, a: str, b: str) -> float:
        ta, tb = set(_WORD.findall(a.lower())), set(_WORD.findall(b.lower()))
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / len(ta | tb)          # Jaccard; a real model returns cosine

    def rank(self, query: str, k: int = 3) -> list:
        scored = sorted(((self.score(query, c), c) for c in self.corpus), reverse=True)
        return [(s, c) for s, c in scored[:k] if s > 0]

    def same_as(self, a: str, b: str, threshold: float = 0.6) -> bool:
        return self.score(a, b) >= threshold


class Verifier:
    """Default ARBITER: mechanical. A finding that carries concrete evidence is CONFIRMED; one
    without is sent to the owner as NO-PRIMARY-SOURCE. A model verifier overrides `judge`."""

    def judge(self, claim: str, evidence: list) -> str:
        return CONFIRMED if evidence else NO_SOURCE


class Fleet:
    """Default: run tasks sequentially (a fleet of one). A real fleet plugs in by overriding `map`
    with Claude Code's Workflow tool. The interface is deliberately tiny so the swap is trivial."""

    def map(self, fn, items: list) -> list:
        return [fn(x) for x in items]


def selftest() -> int:
    ok = fail = 0

    def chk(name, cond):
        nonlocal ok, fail
        print("  %-54s %s" % (name[:54], "PASS" if cond else "FAIL"))
        ok, fail = ok + bool(cond), fail + (not cond)

    si = SemanticIndex(["build an online store", "write a landing page", "trading backtest engine"])
    # NOTE: the default is EXACT token overlap, so it matches shared words, not synonyms
    # ("store" != "storefront"). That is precisely why a real embedding model plugs in here; the
    # test asserts what the mechanical fallback genuinely does.
    ranked = si.rank("build an online store today", k=2)
    chk("mechanical rank puts the token-overlapping item first",
        ranked and "store" in ranked[0][1])
    chk("same_as: near-duplicates match", si.same_as("build an online store", "an online store build"))
    chk("same_as: unrelated do not match", not si.same_as("trading backtest engine", "write a landing page"))

    v = Verifier()
    chk("evidence -> CONFIRMED", v.judge("x is broken", ["line 5: NameError"]) == CONFIRMED)
    chk("no evidence -> surfaced (NO-PRIMARY-SOURCE)", v.judge("x is broken", []) == NO_SOURCE)

    f = Fleet()
    chk("fleet maps over items", f.map(lambda x: x * 2, [1, 2, 3]) == [2, 4, 6])
    print("\n  %d passed, %d failed" % (ok, fail))
    return 1 if fail else 0


if __name__ == "__main__":
    import sys
    sys.exit(selftest())
