# CALLED BY: `python3 -m unittest discover -s tests` -- and by anyone who clones this repo.
# FIRES WHEN: asked -- the test suite of a standalone tool.
"""Stage 6, proven in BOTH directions: it produces a harm-ranked plan for a broken system and an
empty plan for a clean one, and it ranks a worse finding above a lesser one."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ragghost.plan import plan, SEV                                  # noqa: E402


def build(root, files):
    for rel, body in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p) or root, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)


class PlanTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    # ---- MUST FIRE ----
    def test_broken_system_yields_ranked_plan(self):
        build(self.d, {
            "billing/__init__.py": "",
            "billing/charge.py": "def charge(): return 1\n",   # code, ungated -> HIGH
            "orphan.py": "def never(): return 1\n",            # nothing imports -> MEDIUM
        })
        p = plan(self.d)
        self.assertTrue(p.items)
        self.assertEqual(p.exit_code(), 1)
        kinds = [k for _, k, _, _ in p.items]
        self.assertIn("no-gate", kinds)
        self.assertIn("orphan", kinds)
        # ranked by harm: the HIGH item comes before the MEDIUM one
        sevs = [SEV[s] for s, _, _, _ in p.items]
        self.assertEqual(sevs, sorted(sevs))

    # ---- MUST STAY QUIET ----
    def test_clean_system_has_empty_plan(self):
        build(self.d, {
            "pkg/__init__.py": "",
            "pkg/__main__.py": "from pkg import core\n",
            "pkg/core.py": "VALUE = 1\n",
            "tests/test_core.py": "from pkg import core\n",
            "README.md": "docs about compute and payroll and cedar\n",
        })
        p = plan(self.d)
        self.assertEqual(p.items, [])
        self.assertEqual(p.exit_code(), 0)

    # ---- COULD NOT TELL ----
    def test_empty_is_unknown(self):
        p = plan(self.d)
        self.assertFalse(p.assessed)
        self.assertEqual(p.exit_code(), 2)


if __name__ == "__main__":
    unittest.main()
