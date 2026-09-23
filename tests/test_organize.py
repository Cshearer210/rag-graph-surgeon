# CALLED BY: `python3 -m unittest discover -s tests` -- and by anyone who clones this repo.
# FIRES WHEN: asked -- the test suite of a standalone tool.
"""Stage 3, proven in BOTH directions: it flags a clearly-misfiled file and marks load-bearing
files pinned, and it stays QUIET on a tidy tree without calling a legitimately-placed file misfiled.
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ragghost.organize import organize                               # noqa: E402


def build(root, files):
    for rel, body in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p) or root, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)


class OrganizeTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    # ---- MUST FIRE ----
    def test_misfiled_test_file_is_flagged(self):
        build(self.d, {
            "pkg/__init__.py": "",
            "pkg/core.py": "X = 1\n",
            "test_core.py": "from pkg import core\n",   # a test file NOT under tests/
        })
        idx = organize(self.d)
        misfiled = [f for f, _ in idx.misfiled]
        self.assertIn("test_core.py", misfiled)
        self.assertEqual(idx.exit_code(), 1)

    def test_imported_file_is_pinned_unreferenced_is_movable(self):
        build(self.d, {
            "pkg/__init__.py": "",
            "pkg/__main__.py": "from pkg import core\n",
            "pkg/core.py": "VALUE = 1\n",              # imported -> pinned
            "notes.md": "just a doc nothing imports\n",  # nothing references -> movable
        })
        idx = organize(self.d)
        self.assertIn("pkg/core.py", idx.pinned)
        self.assertIn("notes.md", idx.movable)

    # ---- MUST STAY QUIET ----
    def test_tidy_tree_is_clean(self):
        build(self.d, {
            "pkg/__init__.py": "",
            "pkg/__main__.py": "from pkg import core\n",
            "pkg/core.py": "VALUE = 1\n",
            "tests/test_core.py": "from pkg import core\n",   # correctly under tests/
            "README.md": "docs\n",
        })
        idx = organize(self.d)
        self.assertEqual(idx.misfiled, [])
        self.assertEqual(idx.exit_code(), 0)

    def test_tiers_classify(self):
        build(self.d, {
            "pkg/__init__.py": "",
            "pkg/__main__.py": "from pkg import core\n",
            "pkg/core.py": "from pkg import helper\n",
            "pkg/helper.py": "V = 1\n",
            "config.toml": "[x]\n",
            "tests/test_it.py": "pass\n",
        })
        idx = organize(self.d)
        self.assertIn("pkg/__main__.py", idx.tiers.get("entry", []))
        self.assertIn("pkg/core.py", idx.tiers.get("core", []))     # imported by __main__
        self.assertIn("config.toml", idx.tiers.get("config", []))
        self.assertIn("tests/test_it.py", idx.tiers.get("test", []))

    # ---- COULD NOT TELL ----
    def test_empty_is_unknown(self):
        idx = organize(self.d)
        self.assertEqual(idx.exit_code(), 2)


if __name__ == "__main__":
    unittest.main()
