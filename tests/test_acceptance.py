# CALLED BY: `python3 -m unittest discover -s tests` -- and by anyone who clones this repo.
# FIRES WHEN: asked -- the acceptance test of a standalone tool.
"""ACCEPTANCE: build an old-style broken system with one PLANTED issue of every silent/hidden kind
this tool claims to catch, run all eight stages, and require that every plant is caught -- then run
the identical checks against a repaired twin and require that every one stays quiet. This is the
bar Chris set: 'when it catches every type of silent or hidden issue then it is basically finished.'
Both directions in one test, so a change that starts over-firing fails here just as loudly as one
that starts missing."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ragghost.graph import build_graph          # noqa: E402
from ragghost.organize import organize          # noqa: E402
from ragghost.harness import harnesses          # noqa: E402
from ragghost.plan import plan                   # noqa: E402
from ragghost.analyse import analyse             # noqa: E402
from ragghost.fix import fix                     # noqa: E402


def build(root, files):
    for rel, body in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p) or root, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)


BROKEN = {
    "billing/__init__.py": "",
    "billing/charge.py": "from billing import ledger\ndef charge(): return ledger.record()\n",
    "billing/ledger.py": "def record(): return 1\n",
    "tests/test_billing.py": "from billing import charge\ndef test(): assert charge.charge()\n",
    # PLANT 1 dead work: built, nothing imports it
    "reports/__init__.py": "",
    "reports/exporter.py": "def export(): return 'csv'\n",
    # PLANT 2 moved reference: warehouse.py is gone, the caller was never updated
    "inventory/__init__.py": "",
    "inventory/sync.py": "from inventory import warehouse\ndef sync(): return warehouse.pull()\n",
    # PLANT 3 misfiled test: outside tests/
    "inventory/test_sync.py": "def test(): assert True\n",
    # PLANT 4 ungated subsystem: real code, no test touches it
    "shipping/__init__.py": "",
    "shipping/labels.py": "def make_label(): return 'label'\n",
    "docs/extraction.md": "ethanol winterization decarboxylation solvent recovery rotovap\n",
    "docs/growing.md": "germination soil ph nutrients transplant harvest cure\n",
}

CLEAN = {
    "billing/__init__.py": "",
    "billing/charge.py": "from billing import ledger\ndef charge(): return ledger.record()\n",
    "billing/ledger.py": "def record(): return 1\n",
    "billing/monthly.py": "from reports import exporter\ndef run(): return exporter.export()\n",
    "tests/test_billing.py": "from billing import charge, monthly\n"
                             "def test(): assert charge.charge() and monthly.run()\n",
    "reports/__init__.py": "",
    "reports/exporter.py": "def export(): return 'csv'\n",
    "tests/test_reports.py": "from reports import exporter\ndef test(): assert exporter.export()\n",
    "inventory/__init__.py": "",
    "inventory/warehouse.py": "def pull(): return []\n",
    "inventory/sync.py": "from inventory import warehouse\ndef sync(): return warehouse.pull()\n",
    "tests/test_sync.py": "from inventory import sync\ndef test(): assert sync.sync() == []\n",
    "shipping/__init__.py": "",
    "shipping/labels.py": "def make_label(): return 'label'\n",
    "tests/test_shipping.py": "from shipping import labels\ndef test(): assert labels.make_label()\n",
    "docs/extraction.md": "ethanol winterization decarboxylation solvent recovery rotovap\n",
    "docs/growing.md": "germination soil ph nutrients transplant harvest cure\n",
}


class AcceptanceTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_every_planted_issue_is_caught(self):
        build(self.d, BROKEN)
        g = build_graph(self.d)
        self.assertIn("reports/exporter.py", set(g.orphans))                    # PLANT 1
        self.assertTrue(any("warehouse" in t for _, t in g.dangling))          # PLANT 2
        self.assertTrue(any(os.path.basename(f) == "test_sync.py"
                            for f, _ in organize(self.d).misfiled))            # PLANT 3
        self.assertIn("shipping", set(harnesses(self.d).ungated))              # PLANT 4
        kinds = {k for _, k, _, _ in plan(self.d).items}
        self.assertTrue({"orphan", "moved-ref", "no-gate", "misfiled"} <= kinds)
        self.assertIn(analyse(self.d).exit_code(), (0, 1))                     # a decision, not UNKNOWN
        f = fix(self.d, apply=False)
        self.assertTrue(any(x.mechanical and x.kind == "misfiled" for x in f.fixes))
        self.assertTrue(any(not x.mechanical and x.kind == "orphan" for x in f.fixes))

    def test_repaired_twin_stays_quiet(self):
        build(self.d, CLEAN)
        g = build_graph(self.d)
        self.assertEqual(g.orphans, [])
        self.assertEqual(g.dangling, [])
        self.assertEqual(organize(self.d).misfiled, [])
        self.assertEqual(harnesses(self.d).ungated, [])
        self.assertEqual(plan(self.d).items, [])
        self.assertEqual(fix(self.d, apply=False).exit_code(), 0)


if __name__ == "__main__":
    unittest.main()
