# CALLED BY: `python3 -m unittest discover -s tests` -- and by anyone who clones this repo.
# FIRES WHEN: asked -- the test suite of a standalone tool.
"""Stage 5, proven in BOTH directions: it flags a code subsystem no test guards, and stays QUIET
when a test exercises the subsystem. It also identifies a harness's doors (its public surface)."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ragghost.harness import harnesses                               # noqa: E402


def build(root, files):
    for rel, body in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p) or root, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)


class HarnessTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    # ---- MUST FIRE ----
    def test_ungated_subsystem_is_flagged(self):
        build(self.d, {
            "billing/__init__.py": "",
            "billing/charge.py": "def charge(): return 1\n",   # code, nothing tests it
        })
        h = harnesses(self.d)
        self.assertIn("billing", h.ungated)
        self.assertEqual(h.exit_code(), 1)

    # ---- MUST STAY QUIET ----
    def test_gated_subsystem_is_clean(self):
        build(self.d, {
            "billing/__init__.py": "",
            "billing/charge.py": "def charge(): return 1\n",
            "tests/test_charge.py": "from billing import charge\n",   # a gate on billing
        })
        h = harnesses(self.d)
        self.assertNotIn("billing", h.ungated)
        self.assertEqual(h.exit_code(), 0)

    def test_doors_are_the_cross_harness_surface(self):
        build(self.d, {
            "core/__init__.py": "",
            "core/api.py": "def f(): return 1\n",
            "app/__init__.py": "",
            "app/main.py": "from core import api\n",              # app reaches into core.api
            "tests/test_all.py": "from core import api\nfrom app import main\n",
        })
        h = harnesses(self.d)
        self.assertIn("core/api.py", h.groups["core"]["doors"])   # core.api is a door of core

    # ---- COULD NOT TELL ----
    def test_empty_is_unknown(self):
        h = harnesses(self.d)
        self.assertEqual(h.exit_code(), 2)


if __name__ == "__main__":
    unittest.main()
