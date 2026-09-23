# CALLED BY: `python3 -m unittest discover -s tests` -- and by anyone who clones this repo.
# FIRES WHEN: asked -- the test suite of a standalone tool.
"""Stage 8, proven in BOTH directions: it applies ONLY the mechanical class, writes NOTHING in
dry-run, proves each applied fix by re-measuring the world (not by re-describing the edit),
refuses everything that needs a judgement, and reports UNKNOWN on an empty system."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ragghost.fix import fix                                          # noqa: E402


def build(root, files):
    for rel, body in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p) or root, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)


class FixTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    # ---- DRY RUN WRITES NOTHING ----
    def test_dry_run_proposes_but_does_not_write(self):
        build(self.d, {
            "billing/__init__.py": "",
            "billing/charge.py": "def charge(): return 1\n",
            "billing/test_charge.py": "def test(): assert True\n",   # misfiled -> mechanical
        })
        f = fix(self.d, apply=False)
        mech = [x for x in f.fixes if x.mechanical]
        self.assertTrue(mech)
        self.assertFalse(mech[0].applied)
        # the file has NOT moved and tests/ was NOT created
        self.assertTrue(os.path.exists(os.path.join(self.d, "billing/test_charge.py")))
        self.assertFalse(os.path.exists(os.path.join(self.d, "tests/test_charge.py")))

    # ---- APPLY MOVES IT AND PROVES IT BY RE-MEASURING ----
    def test_apply_moves_and_proves(self):
        build(self.d, {
            "billing/__init__.py": "",
            "billing/charge.py": "def charge(): return 1\n",
            "billing/test_charge.py": "def test(): assert True\n",
        })
        f = fix(self.d, apply=True)
        mech = [x for x in f.fixes if x.mechanical]
        self.assertTrue(mech)
        self.assertTrue(mech[0].applied)
        self.assertIs(mech[0].proven, True)
        self.assertFalse(os.path.exists(os.path.join(self.d, "billing/test_charge.py")))
        self.assertTrue(os.path.exists(os.path.join(self.d, "tests/test_charge.py")))

    # ---- IT REFUSES WHAT NEEDS A JUDGEMENT, AND DOES NOT TOUCH IT ----
    def test_orphan_is_refused_not_deleted(self):
        build(self.d, {
            "pkg/__init__.py": "",
            "pkg/core.py": "VALUE = 1\n",
            "orphan.py": "def never(): return 1\n",       # orphan -> needs a human
        })
        f = fix(self.d, apply=True)
        judg = [x for x in f.fixes if not x.mechanical and x.kind == "orphan"]
        self.assertTrue(judg)
        # refused means: still on disk, untouched
        self.assertTrue(os.path.exists(os.path.join(self.d, "orphan.py")))

    # ---- A DESTINATION CLASH IS NOT MECHANICAL ----
    def test_destination_clash_is_not_mechanical(self):
        build(self.d, {
            "billing/__init__.py": "",
            "billing/test_charge.py": "def test(): assert True\n",
            "tests/test_charge.py": "def test(): assert True\n",   # name already taken
        })
        f = fix(self.d, apply=True)
        clash = [x for x in f.fixes if x.kind == "misfiled" and not x.mechanical]
        self.assertTrue(clash)
        # both copies still exist -- nothing was clobbered
        self.assertTrue(os.path.exists(os.path.join(self.d, "billing/test_charge.py")))
        self.assertTrue(os.path.exists(os.path.join(self.d, "tests/test_charge.py")))

    # ---- MUST STAY QUIET ----
    def test_clean_system_has_nothing_to_fix(self):
        build(self.d, {
            "pkg/__init__.py": "",
            "pkg/__main__.py": "from pkg import core\n",
            "pkg/core.py": "VALUE = 1\n",
            "tests/test_core.py": "from pkg import core\n",
            "README.md": "docs about compute and payroll and cedar\n",
        })
        f = fix(self.d, apply=True)
        self.assertEqual(f.fixes, [])
        self.assertEqual(f.exit_code(), 0)

    # ---- COULD NOT TELL ----
    def test_empty_is_unknown(self):
        f = fix(self.d, apply=True)
        self.assertFalse(f.assessed)
        self.assertEqual(f.exit_code(), 2)


if __name__ == "__main__":
    unittest.main()
