# CALLED BY: `python3 -m unittest discover -s tests` -- and by anyone who clones this repo.
# FIRES WHEN: asked -- the test suite of a standalone tool.
"""Stage 5's test-shape half, proven in BOTH directions.

A test that CANNOT FAIL is worse than no test: it is green forever, it counts as coverage, and so
nobody goes looking. Four shapes are reported, and every guard below is here because it was
MEASURED against four real suites (916 test functions) before this shipped -- two of them are
false positives that actually happened and were read, not hypotheticals.
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ragghost.harness import harnesses, hollow_gates                  # noqa: E402


def build(root, files):
    for rel, body in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p) or root, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)


def shapes_of(body):
    """The shapes found in one test file's source, as {test name: [shapes]}."""
    d = tempfile.mkdtemp()
    try:
        p = os.path.join(d, "test_x.py")
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)
        return {n: sh for n, _l, sh in hollow_gates(p)}
    finally:
        shutil.rmtree(d, ignore_errors=True)


class ShapeTest(unittest.TestCase):
    # ---- MUST FIRE: the four shapes ----
    def test_a_test_that_asserts_nothing_is_found(self):
        got = shapes_of("from billing import charge\n"
                        "def test_charge_runs():\n    charge.charge(5)  # no assert\n")
        self.assertEqual(got, {"test_charge_runs": ["asserts-nothing"]})

    def test_a_test_that_reimplements_the_code_is_found(self):
        got = shapes_of("def add(a, b): return a + b\n"
                        "def test_add(): assert add(2, 3) == 2 + 3\n")
        self.assertIn("asserts-the-language", got.get("test_add", []))

    def test_a_test_that_swallows_its_own_failure_is_found(self):
        got = shapes_of("def risky(): return 41\n"
                        "def test_risky():\n    try:\n        assert risky() == 42\n"
                        "    except Exception:\n        pass\n")
        self.assertIn("swallows-its-failure", got.get("test_risky", []))

    def test_a_permanently_skipped_test_is_found(self):
        got = shapes_of("import pytest\n"
                        "@pytest.mark.skip(reason='flaky')\n"
                        "def test_refund():\n    assert False\n")
        self.assertIn("always-skipped", got.get("test_refund", []))

    # ---- MUST STAY QUIET ----
    def test_pytest_raises_is_an_assertion(self):
        # MEASURED: leaving this out flagged roughly thirty good tests across three real suites.
        # An assertion written as a context manager is still an assertion.
        got = shapes_of("import pytest\n"
                        "def test_it_refuses():\n"
                        "    with pytest.raises(ValueError):\n        parse('nope')\n")
        self.assertEqual(got, {})

    def test_a_helper_based_check_is_an_assertion(self):
        got = shapes_of("def test_its_own_cases_hold():\n    thing.selftest()\n")
        self.assertEqual(got, {})

    def test_a_skip_method_on_someone_elses_object_is_not_a_pytest_skip(self):
        # MEASURED, and this one really happened: a coverage ledger recording a skipped member
        # reads as `cov.skip(...)`, and matching the bare name flagged two good tests.
        got = shapes_of("def test_reconciliation(cov):\n"
                        "    cov.skip('b', 'out', measured=0)\n"
                        "    assert cov.ok()\n")
        self.assertEqual(got, {})

    def test_skipif_is_conditional_and_legitimate(self):
        # a test that does not run on Windows is not a test that never runs
        got = shapes_of("import pytest, sys\n"
                        "@pytest.mark.skipif(sys.platform == 'win32', reason='posix only')\n"
                        "def test_posix():\n    assert 1\n")
        self.assertEqual(got, {})

    def test_comparing_a_result_against_a_literal_value_is_not_a_tautology(self):
        # MEASURED: `[]` and `{"k": 3}` are expected VALUES, and eight good tests were flagged
        # before an expected value was told apart from a re-computation.
        got = shapes_of("def descs(s): return real_mutants(s)\n"
                        "def test_syntax_error_yields_nothing():\n"
                        "    assert descs('def (:') == []\n")
        self.assertEqual(got, {})

    def test_a_must_raise_test_does_not_read_as_swallowing(self):
        # `assert False` at the end of the try body is the FAILURE path; the handler is SUCCESS
        got = shapes_of("def test_must_raise():\n    try:\n        parse('nope')\n"
                        "        assert False\n    except ValueError:\n        pass\n")
        self.assertEqual(got, {})

    def test_a_handler_that_reraises_is_not_swallowing(self):
        got = shapes_of("def test_it():\n    try:\n        assert f() == 1\n"
                        "    except AssertionError:\n        raise\n")
        self.assertEqual(got, {})

    def test_a_test_whose_name_says_it_must_not_raise_is_left_alone(self):
        # there is no way to tell intent from syntax, and the name is where the author stated it
        got = shapes_of("def test_missing_path_does_not_raise():\n    cleanup('/never-existed')\n")
        self.assertEqual(got, {})

    def test_an_unparseable_test_file_is_unknown_not_clean(self):
        d = tempfile.mkdtemp()
        try:
            p = os.path.join(d, "test_broken.py")
            with open(p, "w", encoding="utf-8") as f:
                f.write("def (:\n")
            self.assertIsNone(hollow_gates(p), "could-not-parse must not read as 'no findings'")
        finally:
            shutil.rmtree(d, ignore_errors=True)


class GateMeaningTest(unittest.TestCase):
    """The point of the whole thing: a test that cannot fail is not a gate."""

    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_a_subsystem_whose_only_test_cannot_fail_is_NOT_gated(self):
        build(self.d, {
            "shipping/__init__.py": "",
            "shipping/labels.py": "def make_label(x):\n    return 'LABEL-' + x\n",
            "tests/test_shipping.py": "from shipping import labels\n"
                                      "def test_label_runs():\n    labels.make_label('X')\n",
        })
        h = harnesses(self.d)
        self.assertIn("shipping", h.ungated,
                      "a test that checks nothing counted as a gate")

    def test_a_subsystem_with_a_real_test_is_gated(self):
        build(self.d, {
            "shipping/__init__.py": "",
            "shipping/labels.py": "def make_label(x):\n    return 'LABEL-' + x\n",
            "tests/test_shipping.py": "from shipping import labels\n"
                                      "def test_label():\n"
                                      "    assert labels.make_label('X') == 'LABEL-X'\n",
        })
        h = harnesses(self.d)
        self.assertNotIn("shipping", h.ungated)
        self.assertEqual(h.hollow_gates, [])

    def test_a_file_mixing_real_and_hollow_tests_still_gates(self):
        # one bad test does not un-gate a subsystem a good test already covers
        build(self.d, {
            "shipping/__init__.py": "",
            "shipping/labels.py": "def make_label(x):\n    return 'LABEL-' + x\n",
            "tests/test_shipping.py": "from shipping import labels\n"
                                      "def test_label():\n"
                                      "    assert labels.make_label('X') == 'LABEL-X'\n"
                                      "def test_label_runs():\n    labels.make_label('Y')\n",
        })
        h = harnesses(self.d)
        self.assertNotIn("shipping", h.ungated)
        self.assertEqual(len(h.hollow_gates), 1)


if __name__ == "__main__":
    unittest.main()
