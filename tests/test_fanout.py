# CALLED BY: pytest -- known-answer cases for ragghost/fanout.py.
# FIRES WHEN: asked.
"""Known-answer cases, with the BRANCH asserted and not only the code.

⛔ THE LESSON FROM tests/test_ranks_meaning.py IS APPLIED HERE FROM THE START: asserting only the
verdict code cannot tell two branches apart, so a whole branch can be deleted and every test stays
green. Every row names a phrase the answer must carry, which is what makes the case able to fail.

⭐ AND THE GUARDS ARE THE EXPENSIVE DIRECTION IN BOTH SENSES. A wrong "fan out" costs real money and
hours -- the post-mortem this is built on burned 17.0M tokens for 3 confirmed findings. A wrong "do
not" only costs some patience. So the rows that must say NO are the ones that matter most.
"""
import pytest

from ragghost import fanout

FAN_OUT, DO_NOT, CANNOT_TELL = 0, 1, 2

# (label, kwargs, expected code, phrase the answer must carry)
CASES = [
    ("MUST SAY NO -- synthesis, the shape that lost twice and still gets tried",
     {"shape": "synthesis", "items": 40}, DO_NOT, "does not divide"),
    ("MUST SAY NO -- a known path is replayed mechanically, never re-reasoned",
     {"shape": "known-path", "items": 100}, DO_NOT, "does not divide"),
    ("MUST SAY NO -- 'is this the same as that' is the cheapest model's job",
     {"shape": "same-or-not", "items": 500}, DO_NOT, "does not divide"),
    ("MUST SAY NO -- a store already holds the answer",
     {"shape": "already-answered", "items": 30}, DO_NOT, "does not divide"),
    ("MUST SAY NO -- it divides, but it fits in one context, so overhead IS the cost",
     {"shape": "population", "items": 12, "fits_one_context": True}, DO_NOT,
     "fits in one context"),
    ("MUST SAY NO -- one item is not a population",
     {"shape": "population", "items": 1}, DO_NOT, "not a population"),

    ("SAYS YES -- a population too big for one context, each item judged alone",
     {"shape": "population", "items": 400, "fits_one_context": False}, FAN_OUT, "fan out"),
    ("SAYS YES -- independent opinions are the whole point",
     {"shape": "independent-opinions", "items": 5, "fits_one_context": False}, FAN_OUT,
     "cannot see each other"),
    ("SAYS YES -- loop until dry, because a single pass returns 'what I noticed'",
     {"shape": "loop-until-dry", "items": 50, "fits_one_context": False}, FAN_OUT,
     "stop finding"),
    ("SAYS YES BUT NAMES THE LOSS -- a cap that would silently truncate",
     {"shape": "population", "items": 100, "fits_one_context": False, "cap": 20}, FAN_OUT,
     "DROPPED"),

    ("CANNOT TELL -- an unrecognised shape is never a yes",
     {"shape": "make it fast"}, CANNOT_TELL, "unrecognised"),
    ("CANNOT TELL -- an empty shape is never a yes",
     {"shape": ""}, CANNOT_TELL, "unrecognised"),
    ("CANNOT TELL -- None is never a yes",
     {"shape": None}, CANNOT_TELL, "unrecognised"),
]


@pytest.mark.parametrize("label,kw,want,phrase", CASES, ids=[c[0][:48] for c in CASES])
def test_known_answers(label, kw, want, phrase):
    a = fanout.advise(**kw)
    assert a.code == want, "%s -- expected %d, got %d (%s)" % (label, want, a.code, a.headline)
    assert phrase.lower() in (a.headline + " " + a.detail).lower(), \
        "%s -- right code, WRONG BRANCH: %r does not carry %r" % (label, a.headline, phrase)


def test_the_dropped_count_is_real_and_not_merely_mentioned():
    """'some were dropped' is the silent truncation this exists to stop."""
    a = fanout.advise(shape="population", items=100, fits_one_context=False, cap=20)
    assert a.numbers.get("dropped") == 80


@pytest.mark.parametrize("shape", [s.key for s in fanout.SHAPES])
def test_every_shape_in_the_table_is_reachable(shape):
    """A shape listed and unrecognised would make the table decoration."""
    assert fanout.advise(shape=shape, items=50, fits_one_context=False).code != CANNOT_TELL


def test_a_cap_of_zero_refuses_because_nothing_would_run():
    """⛔ THIS EXPECTATION WAS WRONG IN THE ORIGINAL TEST AND THE TEST CERTIFIED THE BUG. It
    expected FAN OUT for a cap of zero -- an approval for a fan-out that dispatches nothing, which
    is a confident wrong answer, the exact shape this module exists to name. A battle test that
    agrees with the defect is worse than no battle test."""
    a = fanout.advise(shape="population", items=10 ** 6, cap=0)
    assert a.code == DO_NOT
    assert a.numbers.get("dropped") == 10 ** 6, "it must report that ALL of them were dropped"


def test_a_cap_that_drops_SOME_still_approves():
    """THE GUARD that stops the fix above turning into 'any cap is a refusal'."""
    a = fanout.advise(shape="population", items=100, cap=20)
    assert a.code == FAN_OUT and a.numbers.get("dropped") == 80


def test_the_advice_prints_and_exposes_an_exit_code():
    a = fanout.advise(shape="synthesis", items=40)
    assert "DO NOT FAN OUT" in str(a)
    assert a.exit_code() == a.code == DO_NOT
