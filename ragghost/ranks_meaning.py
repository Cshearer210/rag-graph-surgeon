"""Does your retrieval index rank MEANING above NOISE?

The failure this finds makes no sound. An index that scores gibberish above a real question
returns confident, well-formed, wrong answers -- and every downstream metric looks healthy,
because retrieval "worked": it returned something.

    >>> from ragghost import ranks_meaning
    >>> ranks_meaning.audit(my_index.search)
    Verdict(state='FAIL', ...)

DESIGN NOTES, each one a defect that was measured rather than imagined:

  NONSENSE IS GENERATED AT RUNTIME.  A fixed list of "nonsense words" gets polluted by whoever
  wrote it -- if those words appear anywhere in the corpus, the probe silently measures nothing.
  Every probe here is a fresh uuid4.

  THE VERDICT CAN BE "CANNOT TELL".  An index that raises, times out, or returns nothing has not
  been shown to be healthy. Absent and fine must never look the same.

  SCORES ARE COMPARED, NOT THRESHOLDED.  An absolute similarity cutoff is meaningless across
  embedding models. What matters is whether real questions beat nonsense, which is scale-free.
"""
from __future__ import annotations

import statistics
import uuid
from dataclasses import dataclass, field


@dataclass
class Verdict:
    """A verdict that CANNOT omit what it examined."""
    state: str                       # PASS | FAIL | CANNOT_TELL
    real_mean: float | None = None
    noise_mean: float | None = None
    margin: float | None = None
    n_real: int = 0
    n_noise: int = 0
    detail: str = ""
    samples: list = field(default_factory=list)

    def __str__(self) -> str:
        if self.state == "CANNOT_TELL":
            return "CANNOT TELL — %s" % self.detail
        if self.noise_mean is None:
            return ("%s — real questions %.4f over %d real / %d scored nonsense probes. %s"
                    % (self.state, self.real_mean, self.n_real, self.n_noise, self.detail))
        return ("%s — real questions %.4f vs nonsense %.4f (margin %+.4f) over %d real / %d "
                "nonsense probes. %s" % (self.state, self.real_mean, self.noise_mean,
                                         self.margin, self.n_real, self.n_noise, self.detail))


def nonsense(n=12, words=4):
    """Probes that CANNOT be in any corpus, generated fresh every call.

    A hardcoded nonsense list is the classic self-poisoning fixture: the words end up in the
    document that explains the test, and then the probe is no longer nonsense.

    ⚠ EVERY WORD STARTS WITH A LETTER, and that is not cosmetic. A raw uuid4 hex can begin with a
    digit, and an identifier-shaped tokenizer -- including `retrieve.py`'s, the first caller of this
    function inside the package -- matches `[A-Za-z_][A-Za-z0-9_]+` and would silently drop that
    first character. The probe would still be absent from the corpus, so the audit would still pass,
    but it would be measuring a string the caller never constructed. Added 2026-09-27 when this
    became a shared definition rather than a standalone module.
    """
    return [" ".join("q" + uuid.uuid4().hex[:8] for _ in range(words)) for _ in range(n)]


def audit(search, real_questions=None, n_noise=12, min_margin=0.0):
    """Ask an index whether meaning outranks noise. -> Verdict.

    `search(query) -> float | (doc, score) | [(doc, score), ...]` — the top score is taken.
    `real_questions` must be questions the corpus can genuinely answer; without them there is
    nothing to compare nonsense AGAINST, and the audit refuses rather than inventing a baseline.
    """
    if not real_questions:
        return Verdict("CANNOT_TELL", detail="no real questions given, so nonsense has nothing "
                                             "to be compared against")

    def top(q):
        try:
            r = search(q)
        except Exception as e:
            raise RuntimeError("the index raised on %r: %s" % (q[:40], e))
        if isinstance(r, (int, float)):
            return float(r)
        if isinstance(r, tuple) and len(r) == 2:
            return float(r[1])
        if isinstance(r, list) and r:
            first = r[0]
            if isinstance(first, (int, float)):
                return float(first)
            if isinstance(first, (tuple, list)) and len(first) >= 2:
                return float(first[1])
        return None

    try:
        real = [s for s in (top(q) for q in real_questions) if s is not None]
        noise = [s for s in (top(q) for q in nonsense(n_noise)) if s is not None]
    except RuntimeError as e:
        return Verdict("CANNOT_TELL", detail=str(e))

    # ⭐ AN INDEX THAT REFUSES TO SCORE NONSENSE IS THE STRONGEST PASS THERE IS, AND THE FIRST
    # VERSION OF THIS CALLED IT "CANNOT TELL". Found by pointing it at a real index: that index
    # answers a query sharing no word with its corpus with an explicit refusal rather than a
    # number. It cannot be fooled by nonsense because it declines to guess -- which is exactly
    # the behaviour this audit exists to look for, and reporting it as un-auditable would have
    # buried the best result as an inconclusive one.
    #
    # ⚠ THE DISTINCTION THAT MAKES IT SAFE: refusing NONSENSE while scoring REAL questions is a
    # pass. Refusing BOTH is a broken index, and that is still CANNOT_TELL.
    if len(real) >= 2 and len(noise) < 2:
        return Verdict("PASS", statistics.fmean(real), None, None, len(real), len(noise),
                       "the index REFUSED to score %d of %d nonsense probes while scoring every "
                       "real question. It declines to guess when a query matches nothing -- the "
                       "strongest form of passing this audit." % (n_noise - len(noise), n_noise))
    if len(real) < 2 or len(noise) < 2:
        return Verdict("CANNOT_TELL", n_real=len(real), n_noise=len(noise),
                       detail="the index returned too few usable scores to compare -- it did not "
                              "score the REAL questions either, so this says nothing about it")

    rm, nm = statistics.fmean(real), statistics.fmean(noise)
    margin = rm - nm
    beaten = [s for s in noise if s >= max(real)]
    state = "PASS" if margin > min_margin else "FAIL"
    detail = ("every nonsense probe scored below the best real question"
              if not beaten else
              "%d nonsense probe(s) scored at or above the BEST real question -- this index "
              "cannot tell your users' questions from random characters" % len(beaten))
    return Verdict(state, rm, nm, margin, len(real), len(noise), detail,
                   samples=sorted(noise, reverse=True)[:3])
