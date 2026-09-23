# CALLED BY: unittest discover. FIRES WHEN: asked.
"""JSON/SARIF output, config select/ignore, inline suppression, and plugins -- proven both ways."""
import json, os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ragghost.report import collect, check, to_json, to_sarif, KIND_TO_CODE   # noqa: E402
from ragghost import plugins                                                   # noqa: E402
from ragghost.report import Finding                                           # noqa: E402


def build(root, files):
    for rel, body in files.items():
        p = os.path.join(root, rel); os.makedirs(os.path.dirname(p) or root, exist_ok=True)
        open(p, "w").write(body)

BROKEN = {
    "billing/__init__.py": "", "billing/charge.py": "from billing import ledger\ndef c(): return ledger.r()\n",
    "billing/ledger.py": "def r(): return 1\n", "tests/test_b.py": "from billing import charge\ndef t(): assert True\n",
    "reports/__init__.py": "", "reports/exporter.py": "def e(): return 1\n",   # orphan
    "shipping/__init__.py": "", "shipping/labels.py": "def m(): return 1\n",    # ungated
}


class ReportTest(unittest.TestCase):
    def setUp(self): self.d = tempfile.mkdtemp(); build(self.d, BROKEN)
    def tearDown(self): shutil.rmtree(self.d, ignore_errors=True)

    def test_findings_are_coded(self):
        codes = {f.code for f in collect(self.d)}
        self.assertIn("GRAPH-ORPHAN", codes)
        self.assertIn("HARNESS-NOGATE", codes)

    def test_json_and_sarif_shapes(self):
        fs = collect(self.d)
        j = json.loads(to_json(fs, self.d)); self.assertEqual(j["tool"], "rag-ghost"); self.assertTrue(j["findings"])
        s = json.loads(to_sarif(fs, self.d)); self.assertEqual(s["version"], "2.1.0")
        self.assertTrue(s["runs"][0]["results"])

    def test_config_ignore_drops_a_code(self):
        open(os.path.join(self.d, ".ragghost.json"), "w").write(json.dumps({"ignore": ["GRAPH-ORPHAN"]}))
        codes = {f.code for f in check(self.d).findings}
        self.assertNotIn("GRAPH-ORPHAN", codes)
        self.assertIn("HARNESS-NOGATE", codes)   # others still fire

    def test_config_select_keeps_only(self):
        open(os.path.join(self.d, ".ragghost.json"), "w").write(json.dumps({"select": ["HARNESS-NOGATE"]}))
        codes = {f.code for f in check(self.d).findings}
        self.assertEqual(codes, {"HARNESS-NOGATE"})

    def test_inline_suppression(self):
        # add the allow comment to the orphan file -> its orphan finding is dropped
        p = os.path.join(self.d, "reports/exporter.py")
        open(p, "w").write("# ragghost: allow GRAPH-ORPHAN\ndef e(): return 1\n")
        codes = {(f.code, f.path) for f in check(self.d).findings}
        self.assertNotIn(("GRAPH-ORPHAN", "reports/exporter.py"), codes)

    def test_plugin_findings_appear(self):
        def my_check(root):
            return [Finding("MY-CUSTOM", "HIGH", "a plugin found something", "x", path=None)]
        plugins._REGISTRY.clear(); plugins.register(my_check)
        try:
            fs = check(self.d, extra_findings=plugins.run_plugins(self.d)).findings
            self.assertIn("MY-CUSTOM", {f.code for f in fs})
        finally:
            plugins._REGISTRY.clear()


if __name__ == "__main__":
    unittest.main()
