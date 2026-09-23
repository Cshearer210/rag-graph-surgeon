# CALLED BY: `python3 -m unittest discover -s tests` -- and by anyone who clones this repo.
# FIRES WHEN: asked -- the test suite of a standalone tool.
"""Stage 2, proven in BOTH directions.

Half of these assert the graph FINDS the two silent wiring failures (an orphan, a moved-file
reference); half assert it stays QUIET on clean wiring and does not mistake a legitimate entry
point for an orphan. A stage that could only ever say "clean" would share the blind spot it exists
to remove.
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ragghost.graph import build_graph                               # noqa: E402


def build(root, files):
    for rel, body in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p) or root, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)


class GraphTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    # ---- MUST FIRE ----
    def test_orphan_is_found(self):
        build(self.d, {
            "app/__init__.py": "",
            "app/main.py": "from app import used\n",
            "app/used.py": "X = 1\n",
            "app/orphan.py": "def never_called():\n    return 1\n",  # nothing imports it
        })
        g = build_graph(self.d)
        self.assertIn("app/orphan.py", g.orphans)
        self.assertNotIn("app/used.py", g.orphans)   # used.py IS imported by main
        self.assertEqual(g.exit_code(), 1)

    def test_broken_submodule_import_is_found(self):
        # from pkg import x, but pkg/x.py is gone and x is not defined in pkg/__init__.py
        # -> a moved/deleted module the caller never updated (reads like a memory bug)
        build(self.d, {
            "inventory/__init__.py": "",
            "inventory/sync.py": "from inventory import warehouse\ndef sync(): return warehouse.pull()\n",
        })
        g = build_graph(self.d)
        self.assertTrue(any("warehouse" in tgt for _, tgt in g.dangling))
        self.assertEqual(g.exit_code(), 1)

    def test_real_submodule_and_init_name_do_not_fire(self):
        # from pkg import real_submodule (exists) and from pkg import NAME (defined in __init__)
        # -> neither is a broken reference; the detector must stay quiet on both
        build(self.d, {
            "pkg/__init__.py": "HELPER = 1\n",
            "pkg/real.py": "def go(): return 1\n",
            "pkg/user.py": "from pkg import real\nfrom pkg import HELPER\ndef u(): return real.go() + HELPER\n",
        })
        g = build_graph(self.d)
        self.assertEqual(g.dangling, [])

    def test_moved_file_reference_is_found(self):
        build(self.d, {
            "run.py": "print('go')\n",
            "config.yaml": "worker: jobs/nightly.py\n",     # names a path that is gone...
            "jobs/other/nightly.py": "print('the real one, moved here')\n",  # ...basename exists elsewhere
        })
        g = build_graph(self.d)
        dangling_targets = [t for _, t in g.dangling]
        self.assertIn("jobs/nightly.py", dangling_targets)
        self.assertEqual(g.exit_code(), 1)

    # ---- MUST STAY QUIET ----
    def test_clean_wiring_is_clean(self):
        build(self.d, {
            "pkg/__init__.py": "",
            "pkg/__main__.py": "from pkg import core\n",     # entry point, imports core
            "pkg/core.py": "from pkg import helper\n",
            "pkg/helper.py": "VALUE = 2\n",
            "tests/test_core.py": "from pkg import core\n",  # a test: never an orphan
        })
        g = build_graph(self.d)
        self.assertEqual(g.orphans, [])
        self.assertEqual(g.dangling, [])
        self.assertEqual(g.exit_code(), 0)

    def test_entry_points_are_not_orphans(self):
        build(self.d, {
            "__main__.py": "print('cli')\n",       # nothing imports a CLI -- correct, not an orphan
            "setup.py": "pass\n",
            "conftest.py": "pass\n",
        })
        g = build_graph(self.d)
        self.assertEqual(g.orphans, [])

    def test_example_path_in_a_doc_is_not_dangling(self):
        # a doc naming a path with NO sibling anywhere is external/illustrative, never flagged
        build(self.d, {
            "README.md": "Point it at `some/external/thing.py` on your own machine.\n",
            "real.py": "X = 1\n",
        })
        g = build_graph(self.d)
        self.assertEqual(g.dangling, [])

    def test_test_files_and_universal_names_are_not_dangling(self):
        # a test file builds fixture paths as strings, and __init__.py is everywhere -- neither
        # is a moved-file reference, and flagging them is the over-firing this tool refuses.
        fixture = 'paths = ' + repr({"app/__init__.py": "", "app/gone.py": ""})
        build(self.d, {
            "tests/test_thing.py": fixture,
            "app/__init__.py": "",
            "pkg/__init__.py": "",
        })
        g = build_graph(self.d)
        self.assertEqual(g.dangling, [])

    # ---- COULD NOT TELL ----
    def test_empty_tree_is_unknown(self):
        g = build_graph(self.d)
        self.assertEqual(g.exit_code(), 2)

    def test_unparseable_python_is_unknown_not_no_edges(self):
        build(self.d, {"broken.py": "def (:\n"})   # a syntax error
        g = build_graph(self.d)
        self.assertIn("broken.py", g.unparsed)


if __name__ == "__main__":
    unittest.main()
