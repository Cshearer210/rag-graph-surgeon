# CALLED BY: `python3 -m unittest discover -s tests` -- and by anyone who clones this repo.
# FIRES WHEN: asked -- the test suite of a standalone tool.
"""Stage 7, proven in BOTH directions: the fan-out decision fires FAN OUT only when the work
divides into enough INDEPENDENT units, and refuses it when the units are too few OR interdependent
-- and it reports UNKNOWN on an empty system rather than a verdict."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ragghost.analyse import analyse, should_fan_out                 # noqa: E402


def build(root, files):
    for rel, body in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p) or root, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)


class ShouldFanOutTest(unittest.TestCase):
    """The pure decision, the cheapest place to prove the rule in both directions."""

    def test_many_independent_units_fan_out(self):
        ok, why = should_fan_out(12, 0)
        self.assertTrue(ok)
        self.assertIn("independent", why)

    def test_too_few_units_one_pass(self):
        ok, why = should_fan_out(3, 0)
        self.assertFalse(ok)
        self.assertIn("overhead", why)

    def test_interdependent_units_one_pass(self):
        # enough units, but they depend on each other -> the fan-out is refused
        ok, why = should_fan_out(12, 5)
        self.assertFalse(ok)
        self.assertIn("cross-dependency", why)  # the message names the coupling

    def test_zero_units_is_not_a_fan_out(self):
        ok, _ = should_fan_out(0, 0)
        self.assertFalse(ok)


class AnalyseTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    # ---- MUST FIRE (FAN OUT is the "found real divisible work" verdict, exit 1) ----
    def test_many_independent_subsystems_fan_out(self):
        files = {}
        for i in range(9):
            files["svc%d/__init__.py" % i] = ""
            files["svc%d/run.py" % i] = "def go(): return %d\n" % i   # no cross-imports
        build(self.d, files)
        a = analyse(self.d)
        self.assertTrue(a.assessed)
        self.assertTrue(a.fan_out)
        self.assertEqual(a.exit_code(), 1)

    # ---- MUST STAY QUIET (ONE PASS is a clean decision, exit 0) ----
    def test_interdependent_subsystems_one_pass(self):
        # nine subsystems, but each imports the shared core -> cross-dependencies -> one pass
        files = {"core/__init__.py": "", "core/base.py": "VALUE = 1\n"}
        for i in range(9):
            files["svc%d/__init__.py" % i] = ""
            files["svc%d/run.py" % i] = "from core import base\n"
        build(self.d, files)
        a = analyse(self.d)
        self.assertTrue(a.assessed)
        self.assertFalse(a.fan_out)
        self.assertEqual(a.exit_code(), 0)

    def test_few_subsystems_one_pass(self):
        build(self.d, {
            "a/__init__.py": "", "a/run.py": "def go(): return 1\n",
            "b/__init__.py": "", "b/run.py": "def go(): return 2\n",
        })
        a = analyse(self.d)
        self.assertFalse(a.fan_out)
        self.assertEqual(a.exit_code(), 0)

    # ---- COULD NOT TELL ----
    def test_empty_is_unknown(self):
        a = analyse(self.d)
        self.assertFalse(a.assessed)
        self.assertEqual(a.exit_code(), 2)


if __name__ == "__main__":
    unittest.main()
