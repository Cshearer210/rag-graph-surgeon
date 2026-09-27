"""Both directions, synthetic fixtures only.

A test whose fixture is real data fails the moment the world improves, and a detector only ever
seen to FIRE is unproven in the other direction.
"""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ragghost import ranks_meaning as R, fanout as S


class RanksMeaning(unittest.TestCase):
    def test_healthy_index_passes(self):
        idx = lambda q: 0.91 if "real" in q else 0.08
        self.assertEqual(R.audit(idx, ["a real question", "another real question"]).state, "PASS")

    def test_anticorrelated_index_fails(self):
        """The measured defect: nonsense scoring ABOVE real questions."""
        idx = lambda q: 0.687 if "real" in q else 0.735
        v = R.audit(idx, ["a real question", "another real question"])
        self.assertEqual(v.state, "FAIL")
        self.assertIn("random characters", v.detail)

    def test_flat_index_fails(self):
        """An index returning the same score for everything has no opinion, and that is a FAIL."""
        self.assertEqual(R.audit(lambda q: 0.5, ["a real q", "b real q"]).state, "FAIL")

    def test_no_real_questions_is_cannot_tell(self):
        self.assertEqual(R.audit(lambda q: 0.9, []).state, "CANNOT_TELL")

    def test_raising_index_is_cannot_tell_not_fail(self):
        def boom(q):
            raise ValueError("connection refused")
        self.assertEqual(R.audit(boom, ["a real q", "b real q"]).state, "CANNOT_TELL")

    def test_nonsense_is_fresh_every_call(self):
        """A hardcoded nonsense list gets polluted by the document that explains it."""
        self.assertFalse(set(R.nonsense(8)) & set(R.nonsense(8)))

    def test_verdict_carries_its_denominator(self):
        v = R.audit(lambda q: 0.9 if "real" in q else 0.1, ["a real q", "b real q"])
        self.assertTrue(v.n_real and v.n_noise)
        self.assertIn("probes", str(v))


class ShouldFanOut(unittest.TestCase):
    def test_big_and_independent_fans_out(self):
        d = S.decide(population=400, fits_one_context=False, judged_independently=True)
        self.assertEqual(d.verdict, "FAN_OUT")
        self.assertTrue(d.cap, "a fan-out with no cap is how 86 agents happen")

    def test_fits_one_context_does_not(self):
        self.assertEqual(S.decide(population=6, fits_one_context=True,
                                  judged_independently=True).verdict, "ONE_CONTEXT")

    def test_synthesis_never_divides(self):
        self.assertEqual(S.decide(population=400, fits_one_context=False,
                                  judged_independently=True, is_synthesis=True).verdict,
                         "ONE_CONTEXT")

    def test_recorded_path_is_replayed(self):
        self.assertEqual(S.decide(population=400, fits_one_context=False,
                                  judged_independently=True, already_recorded=True).verdict,
                         "ONE_CONTEXT")

    def test_big_but_not_independent_does_not_fan_out(self):
        self.assertEqual(S.decide(population=400, fits_one_context=False,
                                  judged_independently=False).verdict, "ONE_CONTEXT")

    def test_unanswered_input_refuses_rather_than_guessing(self):
        self.assertEqual(S.decide(population=400).verdict, "CANNOT_TELL")


class RefusalIsTheStrongestPass(unittest.TestCase):
    """Found by battle-testing against a real index, not imagined."""

    def test_refusing_nonsense_while_scoring_real_is_a_PASS(self):
        idx = lambda q: 0.68 if "real" in q else None
        v = R.audit(idx, ["a real question", "another real question"])
        self.assertEqual(v.state, "PASS")
        self.assertIn("REFUSED", v.detail)

    def test_refusing_EVERYTHING_is_still_cannot_tell(self):
        """Refusing nonsense is health. Refusing real questions too is a broken index."""
        self.assertEqual(R.audit(lambda q: None, ["a real q", "b real q"]).state, "CANNOT_TELL")


class NonsenseIsSafeForAnIdentifierTokenizer(unittest.TestCase):
    """⛔ `retrieve.py` is now a caller of `nonsense()`, and its tokenizer matches
    `[A-Za-z_][A-Za-z0-9_]+`. A raw uuid4 hex can start with a digit, which that regex would silently
    trim -- leaving the audit measuring a string the caller never built. Guarded here rather than
    left to the one caller, because the next caller will have its own tokenizer."""

    def test_every_probe_word_starts_with_a_letter(self):
        for probe in R.nonsense(20, words=3):
            for word in probe.split():
                self.assertTrue(word[0].isalpha(), "%r would lose its first character" % word)


# ⚠ THIS BLOCK WAS SITTING IN THE MIDDLE OF THE FILE, above the last two classes. Under pytest that
# changes nothing, which is why it survived; running the file directly collected only the classes
# defined ABOVE it and reported a pass on a partial suite. Moved to the end 2026-09-27.
if __name__ == "__main__":
    unittest.main(verbosity=2)
