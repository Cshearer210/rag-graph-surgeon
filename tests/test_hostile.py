# CALLED BY: pytest -- the hostile-input pass over the two library judgements.
# FIRES WHEN: asked.
"""Battle-testing: broken, empty, hostile and huge input.

THE CLOSING TEST: *a run where each of those is fed in and NONE PRODUCES A CONFIDENT WRONG ANSWER.*

⭐ SO THE BAR IS NOT "IT DOES NOT CRASH". A crash is loud and gets fixed the same day. The failure
this tool is named after is the opposite: a comfortable, confident number produced from input that
could not support one. Every case below asserts the same thing in different words --

    given input that cannot support a verdict, the answer must be CANNOT TELL (2),
    or an honest FOUND (1). It must NEVER be a confident CLEAN (0).

⚠ AND A CRASH IS STILL A FAILURE HERE, because a library that raises on a caller's bad data has
handed the problem back instead of judging it. Both are tested: no exception escapes, AND the verdict
is honest.
"""
import pytest

from ragghost import fanout
from ragghost import ranks_meaning as R

CLEAN, FOUND, CANNOT_TELL = 0, 1, 2


# (label, real, noise, codes that are ACCEPTABLE -- 0 is never among them unless stated)
SEPARATION_HOSTILE = [
    ("EMPTY -- nothing at all", [], [], (CANNOT_TELL,)),
    ("EMPTY -- real questions but no nonsense to compare against", [0.7] * 20, [], (CANNOT_TELL,)),
    ("BROKEN -- every score is None", [None] * 20, [None] * 20, (CANNOT_TELL,)),
    ("BROKEN -- scores are strings", ["high"] * 20, ["low"] * 20, (CANNOT_TELL,)),
    ("BROKEN -- booleans, which are ints in Python and must not count as scores",
     [True] * 20, [False] * 20, (CANNOT_TELL,)),
    ("BROKEN -- mixed junk with a few real numbers below the floor",
     [0.7, None, "x", 0.6], [0.1, None, "y", 0.2], (CANNOT_TELL,)),
    ("HOSTILE -- every real question scores exactly 0", [0.0] * 20, [0.0] * 20, (FOUND,)),
    ("HOSTILE -- negative scores, which some backends return", [-0.9] * 20, [-0.1] * 20, (FOUND,)),
    ("HOSTILE -- an index that returns 1.0 for everything, the classic flatterer",
     [1.0] * 20, [1.0] * 20, (FOUND,)),
    ("HUGE -- 50,000 probes each side must still answer, and answer honestly",
     [0.8] * 50000, [0.2] * 50000, (CLEAN,)),        # this one IS legitimately clean
    ("HUGE and HOSTILE -- 50,000 each and nonsense wins",
     [0.2] * 50000, [0.8] * 50000, (FOUND,)),
]

ADVISE_HOSTILE = [
    ("EMPTY -- no shape at all", {"shape": None}, (CANNOT_TELL,)),
    ("EMPTY -- blank shape", {"shape": "   "}, (CANNOT_TELL,)),
    ("BROKEN -- a number where a shape belongs", {"shape": 12345}, (CANNOT_TELL,)),
    ("BROKEN -- a list where a shape belongs", {"shape": ["population"]}, (CANNOT_TELL,)),
    ("HOSTILE -- a shape name that LOOKS right but is not",
     {"shape": "populations"}, (CANNOT_TELL,)),
    ("HOSTILE -- a shape that divides, with a negative item count",
     {"shape": "population", "items": -5}, (FOUND,)),
    ("HOSTILE -- zero items is not a population", {"shape": "population", "items": 0}, (FOUND,)),
    ("HUGE -- ten million items still answers",
     {"shape": "population", "items": 10 ** 7}, (CLEAN,)),
    # ⛔ THIS ROW USED TO EXPECT CLEAN, AND THAT WAS THE BUG RATHER THAN THE FIX. A cap of zero
    # means nothing runs, so "fan out" is a confident wrong answer. The test AGREED with it until
    # the expectation was checked by hand. A battle test that agrees with the defect certifies it.
    ("HOSTILE -- a cap of zero means NOTHING runs, so it must refuse, not approve",
     {"shape": "population", "items": 10 ** 6, "cap": 0}, (FOUND,)),
    ("HOSTILE -- a negative cap is the same answer",
     {"shape": "population", "items": 500, "cap": -3}, (FOUND,)),
    ("HOSTILE -- a very long shape string does not hang or pass",
     {"shape": "x" * 100000}, (CANNOT_TELL,)),
]


@pytest.mark.parametrize("label,real,noise,ok",
                         SEPARATION_HOSTILE, ids=[c[0][:46] for c in SEPARATION_HOSTILE])
def test_separation_never_returns_a_confident_wrong_answer(label, real, noise, ok):
    try:
        v = R.separation(real, noise)
    except Exception as exc:                                        # noqa: BLE001
        pytest.fail("%s -- RAISED %s: a library must judge bad data, not hand it back"
                    % (label, type(exc).__name__))
    assert v.code in ok, "%s -- got %d (%s); acceptable: %s" % (label, v.code, v.headline, ok)


@pytest.mark.parametrize("label,kw,ok",
                         ADVISE_HOSTILE, ids=[c[0][:46] for c in ADVISE_HOSTILE])
def test_advise_never_returns_a_confident_wrong_answer(label, kw, ok):
    try:
        a = fanout.advise(**kw)
    except Exception as exc:                                        # noqa: BLE001
        pytest.fail("%s -- RAISED %s" % (label, type(exc).__name__))
    assert a.code in ok, "%s -- got %d (%s); acceptable: %s" % (label, a.code, a.headline, ok)


def test_an_index_returning_non_numeric_scores_never_judges_clean():
    def junk(_t):
        return "not a number", None
    assert R.judge(junk, ["q%d" % i for i in range(20)], n=30, seed=7).code != CLEAN


def test_an_index_returning_none_for_everything_never_judges_clean():
    def nones(_t):
        return None, None
    assert R.judge(nones, ["q%d" % i for i in range(20)], n=30, seed=8).code != CLEAN


def test_an_index_that_returns_the_wrong_arity_never_judges_clean():
    """A caller's adapter may be wrong in a way that is not a crash. That is still not clean."""
    def wrong(_t):
        return (0.9, "a.md", "extra")
    assert R.judge(wrong, ["q%d" % i for i in range(20)], n=30, seed=10).code != CLEAN
