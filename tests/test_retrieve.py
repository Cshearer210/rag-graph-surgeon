# CALLED BY: `python3 -m unittest discover -s tests` -- and by anyone who clones this repo.
# FIRES WHEN: asked -- the test suite of a standalone tool.
"""Stage 4, proven in BOTH directions: a real retriever audits clean and finds a distinctive term,
AND the audit actually fires on a blind retriever and on one that ranks noise. A retrieval stage
whose audit could only ever say 'clean' would have the very blind spot it exists to remove.
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ragghost.retrieve import build_index, Retriever                 # noqa: E402


def build(root, files):
    for rel, body in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p) or root, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)


class RetrieveTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    # ---- MUST STAY QUIET (a real, working retriever) ----
    def test_clean_corpus_audits_clean(self):
        build(self.d, {
            "a.py": "def compute_payroll(): return salary * rate\n",
            "b.md": "the harvesting schedule for cedar beds in autumn\n",
            "c.txt": "unrelated chatter about weather and traffic\n",
        })
        r = build_index(self.d)
        self.assertIsNotNone(r.audit_present)
        self.assertTrue(r.audit_present[2])          # found the present term
        self.assertEqual(r.audit_noise[1], 0.0)      # noise scored zero
        self.assertEqual(r.exit_code(), 0)

    def test_distinctive_term_retrieves_its_file(self):
        build(self.d, {
            "payroll.py": "def compute_payroll(): return 1\n",
            "weather.md": "rain and wind today\n",
        })
        r = build_index(self.d)
        hits = r.query("compute_payroll")
        self.assertTrue(hits)
        self.assertEqual(hits[0][0], "payroll.py")

    # ---- MUST FIRE (the audit catches a broken retriever) ----
    def test_blind_retriever_is_flagged(self):
        r = Retriever()
        r.ndocs = 3
        r.audit_present = ("widget", "only.py", False)   # indexed the term, cannot find it
        r.audit_noise = ("zzq", 0.0)
        self.assertEqual(r.exit_code(), 1)

    def test_noise_ranking_is_flagged(self):
        r = Retriever()
        r.ndocs = 3
        r.audit_present = ("widget", "only.py", True)
        r.audit_noise = ("zzq", 0.42)                    # gibberish scored above zero
        self.assertEqual(r.exit_code(), 1)

    # ---- COULD NOT TELL ----
    def test_empty_is_unknown(self):
        r = build_index(self.d)
        self.assertEqual(r.exit_code(), 2)

    def test_no_unique_term_is_unknown(self):
        # two identical files: every term appears in >=2 files, so no present probe can be built
        build(self.d, {"one.txt": "alpha beta gamma\n", "two.txt": "alpha beta gamma\n"})
        r = build_index(self.d)
        self.assertIsNone(r.audit_present)
        self.assertEqual(r.exit_code(), 2)


if __name__ == "__main__":
    unittest.main()
