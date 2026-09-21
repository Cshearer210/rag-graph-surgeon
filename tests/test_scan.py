# CALLED BY: `python3 -m unittest discover -s tests` -- and by anyone who clones this repo.
# FIRES WHEN: asked -- the test suite of a standalone tool.
"""Stage 1, proven in BOTH directions.

⛔ THE RULE THESE TESTS ARE BUILT ON: a test that only ever asserts a clean result proves nothing.
Half of these assert that the scan REFUSES to say clean -- because the defect this whole tool
exists to catch is a check that reports success when it could not look, and a test suite that
cannot produce that outcome would have the same blind spot as the thing it is testing.
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ragghost import scan                                            # noqa: E402


def build(root, files):
    for rel, body in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)


class ScanTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    # ── it finds what is there ──────────────────────────────────────────────
    def test_counts_every_file(self):
        build(self.d, {"a.py": "x", "b/c.py": "x", "b/d/e.md": "x"})
        r = scan(self.d)
        self.assertEqual(r.files, 3)
        self.assertEqual(r.by_kind["code"], 2)
        self.assertEqual(r.by_kind["docs"], 1)

    def test_classifies_by_what_a_file_is(self):
        build(self.d, {"s.ts": "x", "c.json": "x", "r.md": "x",
                       "d.csv": "x", "p.png": "x", "weird.qqq": "x"})
        r = scan(self.d)
        for kind in ("code", "config", "docs", "data", "media", "other"):
            self.assertEqual(r.by_kind.get(kind), 1, kind)

    def test_reports_depth(self):
        build(self.d, {"a/b/c/d/deep.py": "x"})
        self.assertEqual(scan(self.d).deepest, 4)

    # ── it does not count somebody else's code, AND it says so ──────────────
    def test_vendored_code_is_excluded_and_the_exclusion_is_reported(self):
        build(self.d, {"mine.py": "x",
                       "node_modules/dep/index.js": "x",
                       "node_modules/dep/deep/more.js": "x"})
        r = scan(self.d)
        self.assertEqual(r.files, 1, "a dependency is not part of the system")
        self.assertIn("node_modules", r.skipped_dirs,
                      "a SILENT exclusion is how a denominator shrinks unnoticed")

    def test_an_empty_directory_is_unknown_not_clean(self):
        # The whole tool exists because these two look identical in most scanners.
        r = scan(self.d)
        self.assertEqual(r.files, 0)
        self.assertEqual(r.exit_code(), 2, "an empty result is no measurement")

    def test_a_path_that_does_not_exist_is_unknown_not_clean(self):
        r = scan(os.path.join(self.d, "nope"))
        self.assertEqual(r.exit_code(), 2)
        self.assertTrue(r.unreadable)

    # ── the second count, which is the point of the whole stage ─────────────
    def test_the_two_counts_agree_on_a_healthy_tree(self):
        build(self.d, {"a.py": "x", "b/c.py": "x", "b/d.md": "x", "e/f/g.json": "x"})
        r = scan(self.d)
        self.assertEqual(r.independent, r.files)
        self.assertIs(r.agrees, True)
        self.assertEqual(r.exit_code(), 0)

    def test_the_second_count_skips_the_same_directories(self):
        # If the two methods disagreed about what to exclude, every scan would look broken.
        build(self.d, {"mine.py": "x", "node_modules/a/b.js": "x", ".git/objects/x": "x"})
        r = scan(self.d)
        self.assertIs(r.agrees, True, "the two counts must exclude the same things")

    def test_disagreement_is_reported_as_unknown_rather_than_clean(self):
        build(self.d, {"a.py": "x", "b.py": "x"})
        r = scan(self.d)
        r.independent = r.files + 5          # simulate one method having a blind spot
        self.assertIs(r.agrees, False)
        self.assertEqual(r.exit_code(), 2,
                         "when the counts disagree, the disagreement IS the finding")

    def test_a_missing_second_count_is_never_treated_as_agreement(self):
        build(self.d, {"a.py": "x"})
        r = scan(self.d)
        r.independent = None
        self.assertIsNone(r.agrees)
        self.assertEqual(r.exit_code(), 2, "could-not-take-the-count is not a pass")

    # ── it must not write to what it is pointed at ──────────────────────────
    def test_the_scan_never_writes_to_the_target(self):
        build(self.d, {"a.py": "x", "b/c.md": "y"})
        before = {}
        for dp, _dn, fns in os.walk(self.d):
            for f in fns:
                p = os.path.join(dp, f)
                before[p] = (os.path.getsize(p), os.path.getmtime(p))
        scan(self.d)
        after = {}
        for dp, _dn, fns in os.walk(self.d):
            for f in fns:
                p = os.path.join(dp, f)
                after[p] = (os.path.getsize(p), os.path.getmtime(p))
        self.assertEqual(before, after, "a read-only tool that writes is a broken promise")

    # ── the report says what it could not reach ─────────────────────────────
    def test_the_report_names_what_it_could_not_read(self):
        import io
        build(self.d, {"a.py": "x"})
        r = scan(self.d)
        r.unreadable.append("/somewhere/locked")
        buf = io.StringIO()
        r.report(buf)
        self.assertIn("COULD NOT READ", buf.getvalue())
        self.assertIn("NOT counted as absent", buf.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
