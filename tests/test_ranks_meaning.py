# CALLED BY: pytest -- known-answer cases for ragghost/ranks_meaning.py.
# FIRES WHEN: asked.
"""Known-answer cases. Every row states the right answer before the code runs.

⭐ THE GUARD CASES MATTER MORE THAN THE MUST-FIRE ONES, and that is not a slogan here: this module
tells someone their retrieval is broken. A version that over-fires sends a stranger hunting a defect
that does not exist, and they never trust it again. So every "it must fire" row is paired with an
"and it must stay quiet" row built from the same shape.

⛔ EVERY ROW ASSERTS THE HEADLINE, NOT ONLY THE CODE -- and that is not tidiness, it is the only
reason these cases test anything. Measured while they were written: disabling the inversion branch
entirely left all of them GREEN, because an inverted pair ALSO overlaps, so the very next branch
returned the SAME CODE with a different explanation. A test that reads only the code cannot tell two
branches apart, so one of them was never covered at all -- a case that cannot fail, found by
mutation rather than by reading.
"""
import os

import pytest

from ragghost import ranks_meaning as R

CLEAN, FOUND, CANNOT_TELL = 0, 1, 2


# (label, real scores, nonsense scores, expected code, a phrase the headline must carry)
SEPARATION_CASES = [
    ("MUST FIRE -- the real measurement: nonsense at 0.735 beat real questions at 0.687",
     [0.687] * 10, [0.735] * 10, FOUND, "AT OR ABOVE"),
    ("MUST FIRE -- medians tie, which is not clean",
     [0.5] * 10, [0.5] * 10, FOUND, "AT OR ABOVE"),
    ("MUST FIRE -- medians separate but the ranges overlap, so one query cannot be trusted",
     [0.80, 0.78, 0.76, 0.74, 0.72, 0.70, 0.68, 0.66, 0.64, 0.40],
     [0.45, 0.30, 0.28, 0.26, 0.24, 0.22, 0.20, 0.18, 0.16, 0.14], FOUND, "OVERLAP"),
    ("GUARD -- a genuinely healthy index must come back CLEAN",
     [0.80, 0.78, 0.76, 0.74, 0.72, 0.70, 0.68, 0.66, 0.64, 0.62],
     [0.30, 0.28, 0.26, 0.24, 0.22, 0.20, 0.18, 0.16, 0.14, 0.12], CLEAN, "above nonsense"),
    ("GUARD -- a tiny sample is CANNOT TELL, never a verdict",
     [0.9, 0.8], [0.1, 0.2], CANNOT_TELL, "not enough probes"),
    ("GUARD -- None scores are DROPPED, never counted as zero, so they cannot fake a pass",
     [0.7] * 10, [None] * 10, CANNOT_TELL, "not enough probes"),
]


@pytest.mark.parametrize("label,real,noise,want,phrase",
                         SEPARATION_CASES, ids=[c[0][:48] for c in SEPARATION_CASES])
def test_separation_known_answers(label, real, noise, want, phrase):
    v = R.separation(real, noise)
    assert v.code == want, "%s -- expected %d, got %d (%s)" % (label, want, v.code, v.headline)
    assert phrase.lower() in v.headline.lower(), \
        "%s -- right code, WRONG BRANCH: %r does not carry %r" % (label, v.headline, phrase)


def _fake_index(mapping, default=0.05):
    """A query_fn whose answers are known in advance. -> callable.

    SYNTHETIC on purpose: a fixture built from a real index fails the moment that index improves,
    which is a test that punishes progress.
    """
    def q(text):
        for key, (score, path) in mapping.items():
            if key in text:
                return score, path
        return default, None
    return q


# ── gibberish: generated, never remembered ───────────────────────────────────

def test_the_same_seed_reproduces_and_a_different_seed_does_not():
    """A run has to be repeatable without the strings ever being written to disk."""
    assert R.gibberish(6, seed=1) == R.gibberish(6, seed=1)
    assert R.gibberish(6, seed=1) != R.gibberish(6, seed=2)


@pytest.mark.parametrize("shape", R.SHAPES)
def test_every_shape_produces_the_number_asked_for(shape):
    assert len(R.gibberish(5, shape=shape)) == 5


def test_two_unseeded_calls_never_collide():
    """A hardcoded nonsense list gets polluted by the document that explains it."""
    assert not set(R.gibberish(8)) & set(R.gibberish(8))


def test_wordlike_probes_start_with_a_letter_because_a_tokenizer_would_trim_them():
    """⛔ `retrieve.py` is a caller and its tokenizer matches `[A-Za-z_][A-Za-z0-9_]+`. A probe
    beginning with a digit loses its first character there -- still absent from the corpus, so the
    audit still passes, while measuring a string the caller never built. `wordlike` is the shape
    in-package callers must ask for, so it is the shape that carries this guarantee."""
    for probe in R.gibberish(20, shape="wordlike"):
        for word in probe.split():
            assert word[0].isalpha(), "%r would lose its first character" % word


# ── judge(): the whole probe, end to end ─────────────────────────────────────

def test_a_healthy_index_judges_clean_end_to_end():
    good = _fake_index({"real": (0.85, "/corpus/a.md")}, default=0.10)
    v = R.judge(good, ["real question %d" % i for i in range(10)], n=12, seed=4)
    assert v.code == CLEAN, v.headline


def test_an_index_that_scores_everything_identically_is_found_not_clean():
    flat = _fake_index({}, default=0.5)
    assert R.judge(flat, ["real question %d" % i for i in range(10)], n=12, seed=5).code == FOUND


def test_an_index_that_raises_is_cannot_tell_never_a_verdict():
    def boom(_t):
        raise RuntimeError("index offline")
    assert R.judge(boom, ["real question %d" % i for i in range(10)], n=12, seed=6).code \
        == CANNOT_TELL


def test_a_raising_query_fn_is_NAMED_and_not_reported_as_too_small_a_sample():
    """⛔ THE CONFUSION THIS FIXES, and it cost a real debugging detour. A query_fn that raises on
    every probe used to produce "not enough probes to tell" -- word for word what a caller who
    supplied too few questions gets. Two different problems with one message, and the one that needs
    fixing is not the one the message describes. It happened here: an example lost its `import
    random` in a rewrite, every call raised NameError, and the verdict blamed the sample size."""
    def boom(_t):
        raise NameError("name 'random' is not defined")
    v = R.judge(boom, ["real question %d" % i for i in range(12)], n=12, seed=6)
    assert v.code == CANNOT_TELL
    assert v.numbers.get("query_fn_raised") == 24, "every raise, real and nonsense, is counted"
    assert "NameError" in v.detail, "the verdict must name the exception it kept seeing"
    assert "query_fn" in v.detail, "and say the fault is in the function passed in"


def test_a_healthy_index_reports_no_raises_at_all():
    """THE GUARD: the field must be ABSENT when nothing raised, not present and zero -- otherwise
    every clean verdict carries a scary-looking counter nobody should read anything into."""
    good = _fake_index({"real": (0.85, "/corpus/a.md")}, default=0.10)
    v = R.judge(good, ["real question %d" % i for i in range(10)], n=12, seed=4)
    assert "query_fn_raised" not in v.numbers
    assert "RAISED" not in v.detail


def test_self_echo_hits_are_discarded_and_the_count_is_reported():
    """A corpus containing the asking session answers its own question. That is a mirror, not
    retrieval, and it is the most flattering possible error."""
    here = os.path.abspath(__file__)
    qf = _fake_index({"real": (0.9, here)}, default=0.1)
    v = R.judge(qf, ["real question %d" % i for i in range(10)], n=12, seed=3,
                self_echo_paths=[here])
    assert v.numbers.get("self_echo_discarded") == 10
    assert v.code == CANNOT_TELL, \
        "with every real hit discarded as echo the verdict must be CANNOT TELL, never a clean " \
        "pass on the remaining noise"


def test_refusing_every_nonsense_probe_is_the_strongest_pass():
    """⭐⭐ Found 2026-09-20 by pointing this at a real 82,000-chunk index: it refused all 18
    nonsense probes and the tool said CANNOT TELL, because "refused" and "could not measure"
    produced the same empty list. Those are OPPOSITE answers -- "your index is excellent" and "I
    could not judge your index" -- and collapsing them is the failure this module is named after,
    inside the module."""
    refuser = _fake_index({"real": (0.85, "/corpus/a.md")}, default=None)
    v = R.judge(refuser, ["real question %d" % i for i in range(12)], n=18, seed=11)
    assert v.code == CLEAN, v.headline
    assert v.numbers.get("nonsense_refused") == v.numbers.get("nonsense_asked")


def test_an_index_that_refuses_EVERYTHING_is_broken_not_excellent():
    """⛔ THE GUARD THAT MATTERS MORE THAN THE BRANCH ABOVE. Without it, that fix would hand a
    glowing verdict to a dead index -- a worse error than the one it was written to correct."""
    dead = _fake_index({}, default=None)
    assert R.judge(dead, ["real question %d" % i for i in range(12)], n=18, seed=12).code != CLEAN


def test_too_few_real_questions_refuses_rather_than_inventing_a_baseline():
    v = R.judge(lambda t: (0.9, None), ["only", "three", "questions"])
    assert v.code == CANNOT_TELL
    assert "real questions" in v.headline


# ── the return-shape adapter, kept from the version that lost the merge ───────

@pytest.mark.parametrize("shaped,expected", [
    (0.7, 0.7),
    ((0.7, "docs/a.md"), 0.7),
    (("docs/a.md", 0.7), 0.7),
    ([(0.7, "docs/a.md"), (0.2, "docs/b.md")], 0.7),
    ([0.7, 0.2], 0.7),
    (None, None),
    (True, None),             # a bool is an int in Python and must never be read as a score
    ("high", None),
    ((1, 2, 3), None),
])
def test_a_score_is_read_out_of_whatever_shape_an_index_returns(shaped, expected):
    """Insisting on exactly `(score, path)` means anyone pointing this at an index they already
    have must write an adapter before they can get an answer, and a tool that needs a wrapper
    before it will speak is one people do not run."""
    assert R._score_of(shaped) == expected


def test_judge_works_against_an_index_that_returns_a_bare_number():
    def bare(text):
        return 0.85 if "real" in text else 0.10
    assert R.judge(bare, ["real question %d" % i for i in range(10)], n=12, seed=9).code == CLEAN


def test_the_verdict_carries_its_numbers_and_prints_them():
    v = R.separation([0.8] * 10, [0.2] * 10)
    assert v.numbers["real_median"] and v.numbers["noise_median"]
    assert "gap" in str(v)
    assert v.exit_code() == v.code == CLEAN
