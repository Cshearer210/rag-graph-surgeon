# CALLED BY: ragghost/retrieve.py (the noise probe), examples/*_index.py,
#            tools/run_against_real_index.py; tested by tests/test_ranks_meaning.py and
#            tests/test_hostile.py.
# ⛔ THAT LAST PATH SAID `docs/` FOR ABOUT TEN MINUTES, and `ragghost check .` on this repo caught it
# before it was committed -- the file was written to `tools/`, so the comment named something that
# does not exist. Left here as a note because it is the third time this session the tool found a
# stale path in its own source, which is the whole argument for running it on yourself.
# FIRES WHEN: asked -- a library you point at your OWN index, so it takes a function, not a path.
"""Does your retrieval index rank MEANING, or noise?

    If I feed this index nonsense, does the nonsense score LOWER than a real question?

Everyone has a vector index. Almost nobody tests this, because a retrieval system that ranks noise
above meaning DOES NOT RAISE AN ERROR. It returns a passage, confidently, and every downstream
answer looks exactly as trustworthy as a correct one.

⭐ THE MEASUREMENT THIS IS BUILT ON IS REAL AND WAS FOUND THE HARD WAY: in a live index of 82,000+
chunks, random hexadecimal scored **0.735** while real questions scored **0.687**. Nonsense
outranked meaning and nothing anywhere said a word. That pair is the first case in the test suite
and `examples/lying_index.py` reproduces it with no index at all.

    >>> from ragghost import ranks_meaning
    >>> ranks_meaning.judge(my_query_fn, my_known_questions)
    Verdict(code=0, 'real questions rank above nonsense, with no overlap')

FIVE RULES, each one earned by a way this measurement goes wrong:

    1  GIBBERISH IS GENERATED AT RUNTIME, never a fixed word list. A fixture made of remembered
       words is polluted the moment a session writes those words into the corpus -- measured, and
       it is why `zzqx wibble frobnicate quux` had to be retired.
    2  THREE SHAPES OF NONSENSE, because they fail differently: hex looks like an identifier and a
       tokenizer may split it into familiar pieces; word-shaped nonsense looks like language and
       can ride on subword statistics; punctuation has no structure at all. An index that survives
       only one of the three has not been tested.
    3  MEDIAN TO MEDIAN, NEVER BEST TO BEST. One lucky real question above one unlucky nonsense
       string says nothing, and taking the max of each is how this measurement flatters itself.
    4  A MISSING SCORE IS DROPPED, NEVER READ AS ZERO. An index that returns nothing for a probe
       has not scored it low -- it has not answered, and treating silence as a low score would
       manufacture a clean result out of a broken index.
    5  CANNOT TELL IS A REAL ANSWER, and it is code 2. A comfortable wrong number is the failure
       being measured, so it never returns one.

⛔ THIS FILE IS A MERGE, AND THE SURVIVOR IS NOT THE ONE THAT SHIPPED FIRST. Two versions of this
question existed in unpublished work -- a 110-line one and a 214-line one -- and the shorter one was
published first, on 2026-09-27, because whoever did it did not know the other existed. The longer
one wins on every axis that matters here: three shapes of nonsense instead of one, a median
comparison instead of a mean, an explicit overlap verdict, a minimum-probe floor, self-echo
filtering, and a `code` that is already the 0/1/2 this whole tool exits with. What the shorter one
had and this keeps is `_score_of`: it accepts several shapes of return value, so you can point it at
an index you already have without writing an adapter first.
"""
from __future__ import annotations

import hashlib
import os
import random
import statistics
import string

__all__ = ["gibberish", "Verdict", "separation", "judge", "SHAPES", "MIN_PROBES"]

#: The three shapes of nonsense. See rule 2 above -- an index that survives one is not tested.
SHAPES = ("hex", "wordlike", "punct")

#: Below this many scored probes of each kind the run is CANNOT TELL: fewer than this and a single
#: outlier decides the verdict, which is exactly the unreliable confident answer this tool finds.
MIN_PROBES = 8


def gibberish(n=12, shape="hex", seed=None):
    """n strings that mean nothing. -> [str]. GENERATED, never a remembered list.

    A fixed nonsense fixture is polluted by its own documentation: the moment "zzqx wibble" is
    written into a rule explaining this check, the corpus contains it and the probe starts matching.
    Generating from a seed keeps a run reproducible without ever putting the strings on disk.

    ⚠ ONLY `wordlike` IS SAFE FOR AN IDENTIFIER-SHAPED TOKENIZER, and callers inside this package
    must ask for it by name. A `hex` probe can begin with a digit and a `punct` probe is nothing but
    punctuation, so a tokenizer matching `[A-Za-z_][A-Za-z0-9_]+` -- `retrieve.py`'s, for one --
    would trim the first character off the one and discard the other entirely. The probe would still
    be absent from the corpus, so the audit would still pass, while measuring a string the caller
    never constructed. `wordlike` is consonant-vowel pairs and always starts with a letter.
    """
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        if shape == "hex":
            out.append(hashlib.sha1(str(rng.random()).encode()).hexdigest()[:rng.randint(8, 24)])
        elif shape == "wordlike":
            words = []
            for _w in range(rng.randint(3, 7)):
                c, v = "bcdfghjklmnpqrstvwxz", "aeiou"
                words.append("".join(rng.choice(c) + rng.choice(v)
                                     for _s in range(rng.randint(2, 4))))
            out.append(" ".join(words))
        else:
            out.append("".join(rng.choice(string.punctuation + string.digits + " ")
                               for _c in range(rng.randint(10, 30))))
    return out


class Verdict(object):
    """One honest answer. `code` is 0 clean / 1 found a problem / 2 could not tell -- the same three
    outcomes, and the same three exit codes, as every stage of this tool."""

    def __init__(self, code, headline, detail=None, numbers=None):
        self.code = int(code)
        self.headline = headline
        self.detail = detail or ""
        self.numbers = numbers or {}

    def __repr__(self):
        return "Verdict(code=%d, %r)" % (self.code, self.headline)

    def __str__(self):
        s = "%s %s" % (("CLEAN", "FOUND A PROBLEM", "CANNOT TELL")[self.code], self.headline)
        if self.numbers:
            s += "\n  " + "  ".join("%s=%s" % (k, v) for k, v in sorted(self.numbers.items()))
        if self.detail:
            s += "\n  " + self.detail
        return s

    def exit_code(self):
        """So a caller can `raise SystemExit(v.exit_code())` like every other stage."""
        return self.code


def _score_of(r):
    """The score out of whatever shape an index hands back. -> float or None.

    ⭐ KEPT FROM THE OTHER VERSION OF THIS MODULE, AND IT IS THE REASON TO KEEP IT: insisting on
    exactly `(score, path)` means anyone pointing this at an index they already have must write an
    adapter before they can get an answer, and a tool that needs a wrapper before it will speak is
    one people do not run. A bare number, a `(doc, score)` pair, or a ranked list all work.
    """
    if r is None or isinstance(r, bool):
        return None
    if isinstance(r, (int, float)):
        return float(r)
    if isinstance(r, tuple) and len(r) == 2:
        # either (score, path) or (path, score) -- take whichever member is a number
        a, b = r
        for cand in (a, b):
            if isinstance(cand, (int, float)) and not isinstance(cand, bool):
                return float(cand)
        return None
    if isinstance(r, list) and r:
        return _score_of(r[0])
    return None


def _path_of(r):
    """The path out of the same shapes, for the self-echo filter. -> str or None."""
    if isinstance(r, tuple) and len(r) == 2:
        for cand in r:
            if isinstance(cand, str):
                return cand
    if isinstance(r, list) and r:
        return _path_of(r[0])
    return None


def _clean(xs):
    """Scores that are actually numbers. -> [float]. A None is DROPPED, never read as 0 (rule 4)."""
    out = []
    for x in xs:
        s = _score_of(x)
        if s is not None:
            out.append(s)
    return out


def separation(real_scores, noise_scores, min_probes=MIN_PROBES):
    """How far real questions sit above nonsense. -> Verdict.

    ⛔ MEDIAN TO MEDIAN, NOT BEST TO BEST (rule 3). And the overlap case gets its own verdict: when
    the medians separate but the best nonsense probe still beats the worst real question, the index
    is not hopeless and no single query can be trusted -- two different situations that a single
    pass/fail would report identically.
    """
    real, noise = _clean(real_scores), _clean(noise_scores)
    if len(real) < min_probes or len(noise) < min_probes:
        return Verdict(2, "not enough probes to tell",
                       "%d real and %d nonsense probes scored; below %d either of them one "
                       "outlier decides the verdict, which is the confident wrong answer this "
                       "exists to find." % (len(real), len(noise), min_probes),
                       {"real": len(real), "noise": len(noise), "needed": min_probes})
    rm, nm = statistics.median(real), statistics.median(noise)
    gap = rm - nm
    worst_real, best_noise = min(real), max(noise)
    nums = {"real_median": round(rm, 4), "noise_median": round(nm, 4),
            "gap": round(gap, 4), "worst_real": round(worst_real, 4),
            "best_noise": round(best_noise, 4)}
    if gap <= 0:
        return Verdict(1, "nonsense scores AT OR ABOVE real questions",
                       "Every answer this index returns is as confident as a correct one, and "
                       "nothing in it will say so. This is the failure the tool exists to name.",
                       nums)
    if best_noise >= worst_real:
        return Verdict(1, "the ranges OVERLAP: some nonsense outranks some real questions",
                       "The medians separate, so it is not hopeless -- but a single query cannot "
                       "be trusted, because at least one nonsense probe beat at least one real "
                       "question.", nums)
    return Verdict(0, "real questions rank above nonsense, with no overlap",
                   "The worst real question still scores above the best nonsense probe.", nums)


def judge(query_fn, real_questions, n=12, seed=None, min_probes=MIN_PROBES,
          self_echo_paths=None):
    """Run the whole probe against any index. -> Verdict.

    `query_fn(text)` is the ONLY thing a caller must supply, so this works against any retrieval
    system without knowing anything about it. It may return a score, a `(score, path)` pair, a
    `(path, score)` pair, or a ranked list of those -- see `_score_of`.

    `self_echo_paths` are files containing the asking session's own words. A hit in one of those is
    DISCARDED, because a corpus that contains the question answers it by echo. That is a mirror,
    not retrieval, and it is the most flattering possible error.
    """
    if not real_questions or len(real_questions) < min_probes:
        return Verdict(2, "not enough real questions to compare against",
                       "Supply at least %d questions whose answers you already know. Without them "
                       "nonsense has nothing to be compared against, and a baseline this tool "
                       "invented for you would be measuring itself."
                       % min_probes, {"given": len(real_questions or [])})
    echo = {os.path.abspath(p) for p in (self_echo_paths or [])}
    real, noise, echoed = [], [], 0
    # ⭐ EVERY RAISE IS COUNTED, AND THE REASON IS A REAL CONFUSION THIS CAUSED. A `query_fn` that
    # raises on every probe produced "not enough probes to tell" -- the same words as a caller who
    # simply supplied too few questions. Two completely different problems with one message, and the
    # one that needs fixing is not the one the message describes. Measured 2026-09-27: an example in
    # this repo lost its `import random` in a rewrite, every call raised NameError, and the verdict
    # said the sample was too small. The verdict now names the exception it kept seeing.
    raised = {}

    def _ask(text):
        try:
            return query_fn(text), True
        except Exception as exc:                                 # noqa: BLE001
            name = type(exc).__name__
            raised[name] = raised.get(name, 0) + 1
            return None, False           # a probe that raised did not score; it is not a 0

    for q in real_questions:
        r, ok = _ask(q)
        if not ok:
            continue
        p = _path_of(r)
        if p and os.path.abspath(str(p)) in echo:
            echoed += 1
            continue
        real.append(r)
    noise_asked = 0
    for shape in SHAPES:
        for g in gibberish(max(1, n // len(SHAPES)), shape=shape, seed=seed):
            noise_asked += 1
            r, ok = _ask(g)
            if ok:
                noise.append(r)

    # ⭐⭐ THE BEST POSSIBLE OUTCOME IS AN INDEX THAT REFUSES NONSENSE OUTRIGHT, AND THIS TOOL COULD
    # NOT SEE IT. Found 2026-09-20 by pointing it at a real 82,000-chunk index: every one of the 18
    # nonsense probes came back with NO SCORE, because that index answers "I cannot tell" when
    # nothing in the question matches its corpus. `separation()` then said "not enough probes" --
    # CANNOT TELL -- which is the same verdict it gives when the measurement simply failed.
    #
    # ⛔ THOSE ARE OPPOSITE ANSWERS WEARING ONE WORD: "your index is excellent" and "I could not
    # measure your index". Reporting the first as the second is exactly the failure this module is
    # named after, sitting inside the module. A refusal is a RESULT and is counted as one.
    #
    # ⚠ AND THE DISTINCTION THAT MAKES IT SAFE: refusing NONSENSE while answering REAL questions is
    # a pass. Refusing BOTH is a broken index, and that is still CANNOT TELL -- which is why this
    # requires `answered_real >= min_probes` before it will call a refusal excellent.
    refused = noise_asked - len(_clean(noise))
    answered_real = len(_clean(real))
    if noise_asked and refused == noise_asked and answered_real >= min_probes:
        return Verdict(0, "the index REFUSED every nonsense probe outright",
                       "%d of %d nonsense probes returned no score at all, while %d real "
                       "questions were answered. Refusing to answer nonsense is stronger than "
                       "merely scoring it low -- there is no number for a caller to misread."
                       % (refused, noise_asked, answered_real),
                       {"nonsense_refused": refused, "nonsense_asked": noise_asked,
                        "real_answered": answered_real})

    v = separation(real, noise, min_probes=min_probes)
    if raised:
        total = sum(raised.values())
        v.numbers["query_fn_raised"] = total
        worst = max(raised.items(), key=lambda kv: kv[1])
        v.detail += (" ⚠ YOUR query_fn RAISED on %d of the probes (mostly %s, %d time(s)). That is "
                     "a fault in the function passed in, not a measurement of the index -- fix it "
                     "and run again, because nothing here says anything about your retrieval yet."
                     % (total, worst[0], worst[1]))
    if noise_asked and refused:
        v.numbers["nonsense_refused"] = refused
        v.numbers["nonsense_asked"] = noise_asked
    if echoed:
        v.numbers["self_echo_discarded"] = echoed
        v.detail += (" %d hit(s) were discarded as self-echo -- the corpus contains the asking "
                     "session's own words." % echoed)
    return v
