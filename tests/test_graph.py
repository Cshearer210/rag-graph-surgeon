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

    def test_examples_and_changelog_do_not_cry_wolf(self):
        # example scripts are entry points (never imported) and a CHANGELOG describes past state --
        # neither is a finding, but a real dead module still is
        build(self.d, {
            "pkg/__init__.py": "", "pkg/core.py": "VALUE = 1\n",
            "examples/demo.py": "from pkg import core\n",
            "realdead.py": "def x(): return 1\n",
            "CHANGELOG.md": "the old banner lived at assets/social-card.png\n",
        })
        g = build_graph(self.d)
        names = {__import__("os").path.basename(o) for o in g.orphans}
        self.assertNotIn("demo.py", names)      # example not flagged
        self.assertIn("realdead.py", names)     # real dead code still caught
        self.assertFalse(any("social-card" in t for _, t in g.dangling))

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

    # ---- DUPLICATE DEFINITIONS: must fire ----
    def test_a_literal_copy_of_a_helper_is_found(self):
        body = "import os\ndef slurp(p):\n    return open(p, encoding='utf-8').read()\n"
        build(self.d, {"a/__init__.py": "", "a/one.py": body, "a/two.py": body})
        names = {n for n, _k, _f, _m in build_graph(self.d).duplicates}
        self.assertIn("slurp", names)

    def test_a_drifted_copy_of_one_job_is_found(self):
        # the dangerous half: the same job, computed two ways, so the two no longer agree
        build(self.d, {
            "pricing/__init__.py": "",
            "pricing/discount.py": "def apply_discount(price, pct):\n"
                                   "    return price * (1 - pct/100.0)\n",
            "promo/__init__.py": "",
            "promo/discount.py": "def apply_discount(price, pct):\n"
                                 "    return price - price*pct/100.0\n",
        })
        found = [d for d in build_graph(self.d).duplicates if d[0] == "apply_discount"]
        self.assertEqual(len(found), 1, "one finding, not one per pair")
        self.assertEqual(found[0][3], "same-job")
        self.assertEqual(found[0][2], ["pricing/discount.py", "promo/discount.py"])

    def test_the_finding_names_only_the_files_that_actually_match(self):
        # three files share the name; only two share the code. Naming all three would send the
        # reader to a file that is not part of the defect.
        same = "def handle(req):\n    return req.body\n"
        build(self.d, {
            "s/__init__.py": "", "s/a.py": same, "s/b.py": same,
            "s/c.py": "def handle(req):\n    return {'other': req.headers}\n",
        })
        found = [d for d in build_graph(self.d).duplicates if d[0] == "handle"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][2], ["s/a.py", "s/b.py"])

    # ---- DUPLICATE DEFINITIONS: must stay quiet ----
    def test_an_interface_implemented_per_module_is_not_a_duplicate(self):
        # the same name and signature, deliberately, so a registry can call them uniformly. The
        # bodies name different things, which is what separates an interface from a copy.
        build(self.d, {
            "p/__init__.py": "",
            "p/alpha.py": "def raw_findings(root):\n    return scan_alpha(root, depth=2)\n",
            "p/beta.py": "def raw_findings(root):\n    return parse_beta(root).results\n",
        })
        self.assertEqual(build_graph(self.d).duplicates, [])

    def test_a_conventional_entry_point_is_not_a_duplicate(self):
        build(self.d, {
            "q/__init__.py": "",
            "q/one.py": "def main(argv=None):\n    return run_one(argv)\n",
            "q/two.py": "def main(argv=None):\n    return serve_two(argv)\n",
        })
        self.assertEqual(build_graph(self.d).duplicates, [])

    def test_a_repeated_helper_under_tests_is_not_a_duplicate(self):
        body = "def helper(x):\n    return x + 1\n"
        build(self.d, {"tests/test_a.py": body, "tests/test_b.py": body})
        self.assertEqual(build_graph(self.d).duplicates, [])

    def test_two_definitions_in_ONE_file_are_a_different_class(self):
        # shadowing inside one file is real, and it is not what this detector reports
        build(self.d, {"r/__init__.py": "",
                       "r/only.py": "def f(a):\n    return a\ndef f(a):\n    return a\n"})
        self.assertEqual(build_graph(self.d).duplicates, [])

    def test_a_clean_tree_reports_no_duplicates(self):
        build(self.d, {"c/__init__.py": "", "c/one.py": "def alpha(x):\n    return x*2\n",
                       "c/two.py": "def beta(y):\n    return y-1\n"})
        self.assertEqual(build_graph(self.d).duplicates, [])

    # ---- DEAD SYMBOLS: must fire ----
    def test_an_exported_symbol_nothing_calls_is_found(self):
        # the file IS imported, so the file-level orphan check cannot see this
        build(self.d, {
            "util/__init__.py": "from util.textutil import normalize_ph\n",
            "util/textutil.py": "__all__ = ['normalize_ph']\ndef normalize_ph(x):\n"
                                "    return round(x, 2)\n",
            "app.py": "import util\nprint(util)\n",
        })
        found = {n for n, _f, _l, _e, _m in build_graph(self.d).dead_symbols}
        self.assertIn("normalize_ph", found)

    def test_a_mention_in_a_comment_or_a_string_is_not_a_use(self):
        # grep says used; the syntax says nothing names it. That gap is the whole finding.
        build(self.d, {
            "util/__init__.py": "from util.textutil import normalize_ph\n",
            "util/textutil.py": "__all__ = ['normalize_ph']\ndef normalize_ph(x):\n    return x\n",
            "util/notes.py": "# TODO: maybe use normalize_ph here someday\n"
                             "HINT = 'call normalize_ph for rounding'\n",
            "app.py": "import util\nprint(util)\n",
        })
        hits = [h for h in build_graph(self.d).dead_symbols if h[0] == "normalize_ph"]
        self.assertEqual(len(hits), 1)
        self.assertTrue(hits[0][3], "it is exported, and the finding must say so")
        self.assertEqual(hits[0][4], ["util/notes.py"])

    # ---- DEAD SYMBOLS: must stay quiet ----
    def test_a_symbol_passed_as_a_value_is_not_dead(self):
        # a registry never CALLS its entries at the point it names them, and flagging a wired
        # builder would be the crying-wolf this tool refuses
        build(self.d, {
            "reg/__init__.py": "from reg import impl\nBUILDERS = {'a': impl.build}\n",
            "reg/impl.py": "def build(x):\n    return x\n",
            "app.py": "import reg\nprint(reg)\n",
        })
        self.assertEqual(build_graph(self.d).dead_symbols, [])

    def test_a_symbol_in_a_file_already_reported_as_an_orphan_is_not_reported_twice(self):
        build(self.d, {"lonely.py": "def nobody(x):\n    return x\n",
                       "app/__init__.py": "", "app/main.py": "X = 1\n"})
        g = build_graph(self.d)
        self.assertIn("lonely.py", g.orphans)
        self.assertEqual(g.dead_symbols, [])

    def test_a_decorated_symbol_is_not_dead(self):
        build(self.d, {"p/__init__.py": "from p import h\nprint(h)\n",
                       "p/h.py": "import functools\n\n\n@functools.cache\ndef helper(x):\n"
                                 "    return x\n"})
        self.assertEqual(build_graph(self.d).dead_symbols, [])

    def test_a_test_function_is_not_dead(self):
        build(self.d, {"tests/test_it.py": "def test_thing():\n    assert 1\n",
                       "app/__init__.py": "", "app/main.py": "X = 1\n"})
        self.assertEqual(build_graph(self.d).dead_symbols, [])

    def test_a_called_symbol_is_not_dead(self):
        build(self.d, {"m/__init__.py": "", "m/lib.py": "def go(x):\n    return x\n",
                       "m/use.py": "from m.lib import go\n\n\ndef run():\n    return go(1)\n"})
        found = {n for n, _f, _l, _e, _m in build_graph(self.d).dead_symbols}
        self.assertNotIn("go", found)

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
