"""End-to-end sandbox: run the surgeon against a COPY of examples/broken-shop and prove the whole
selling point -- a broken system goes in, a working store comes out, and the owner's originals are
never touched. This is the private-testbed idea from FABLE-REPO-PLAN, made runnable in CI.
"""
import json
import os
import shutil
import tempfile
import unittest

from ragghost.surgeon import road
from ragghost.surgeon.interview import Scope

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLE = os.path.join(HERE, "examples", "broken-shop")


class TestSurgeonSandbox(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.target = os.path.join(self.tmp, "shop")          # a COPY the surgeon may read
        shutil.copytree(EXAMPLE, self.target)
        self.ws = os.path.join(self.tmp, "workspace")
        self.out = os.path.join(self.tmp, "shipped")
        self.scope = Scope(output="landing", goal="small-batch home goods store",
                           store_name="Aurora Goods", defaults={"store_name": "Aurora Goods"})
        # config.json lives under data/, so tell the road where the required field is
        road.REQUIRED_FIELDS["landing"] = {"data/config.json": ["store_name"]}
        self.r = road.run(self.target, self.ws, self.out, scope=self.scope, verbose=False)

    def test_it_shipped_a_store(self):
        self.assertTrue(self.r.shipped, "the store did not ship: %s" % self.r.grade_detail)
        self.assertEqual(self.r.grade_score, 1.0)

    def test_landing_page_shipped_with_the_store_name(self):
        idx = open(os.path.join(self.out, "index.html"), encoding="utf-8").read()
        self.assertIn("Aurora Goods", idx, "landing page missing the store name")


    def test_fixable_defects_were_fixed(self):
        fixed_blob = " ".join(note for _, note in self.r.fixed).lower()
        self.assertIn("trailing comma", fixed_blob)          # D1
        self.assertTrue(any("store_name" in n for _, n in self.r.fixed))   # D2

    def test_dangerous_defects_were_surfaced_not_touched(self):
        surfaced_blob = " ".join(s for s, _ in self.r.surfaced).lower()
        self.assertIn("legacy_paypal_ipn", surfaced_blob)    # D5 orphan: surfaced, never deleted
        self.assertIn("discount_broken", surfaced_blob)      # D6 syntax error: surfaced
        self.assertIn("template", surfaced_blob)          # D4 import: surfaced, NOT auto-rewritten
        # and it really did NOT delete the orphan from the workspace
        self.assertTrue(os.path.exists(os.path.join(self.ws, "src", "legacy_paypal_ipn.py")))

    def test_conflicting_rule_flagged_not_deleted(self):
        flagged = " ".join(f["file"] for f in self.r.rules_flagged)
        self.assertIn("legacy-scope.md", flagged)
        self.assertTrue(os.path.exists(os.path.join(self.ws, "rules", "legacy-scope.md")))

    def test_owner_original_never_modified(self):
        # the planted trailing comma is still in the ORIGINAL example, untouched
        original = open(os.path.join(EXAMPLE, "data", "products.json"), encoding="utf-8").read()
        self.assertRegex(original, r",\s*\]")

    def test_proof_written(self):
        p = os.path.join(self.out, "_surgeon_proof.json")
        self.assertTrue(os.path.exists(p))
        proof = json.load(open(p))
        self.assertEqual(proof["output"], "landing")
        self.assertTrue(proof["shipped"])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
