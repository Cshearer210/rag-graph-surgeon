# CALLED BY: ragghost/__main__.py  (`python3 -m ragghost demo`)
# FIRES WHEN: asked -- a 15-second, self-contained demonstration run by whoever downloaded it.
"""A rot-proof demo: build a tiny broken system in a temp directory, run every stage against it,
and show the real output. It cannot drift from the tool because it IS the tool, run live. No
arguments, no network, nothing written outside a temp dir it cleans up.
"""
from __future__ import annotations

import shutil
import sys
import tempfile

from .graph import build_graph
from .organize import organize
from .harness import harnesses
from .plan import plan
from .analyse import analyse
from .fix import fix

_FILES = {
    "billing/__init__.py": "",
    "billing/charge.py": "from billing import ledger\ndef charge(n): return ledger.record(n)\n",
    "billing/ledger.py": "def record(n): return n\n",
    "tests/test_billing.py": "from billing import charge\ndef test(): assert charge.charge(5) == 5\n",
    # a module nothing imports
    "reports/__init__.py": "",
    "reports/exporter.py": "def export(rows): return ','.join(map(str, rows))\n",
    # a caller that names a module that was deleted
    "inventory/__init__.py": "",
    "inventory/sync.py": "from inventory import warehouse\ndef sync(): return warehouse.pull()\n",
    # a test file in the wrong place
    "inventory/test_sync.py": "def test(): assert True\n",
    # a subsystem with no test
    "shipping/__init__.py": "",
    "shipping/labels.py": "def make_label(o): return 'L-%s' % o\n",
}


def _build(root):
    import os
    for rel, body in _FILES.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)


def main(argv=None):
    out = sys.stdout
    d = tempfile.mkdtemp(prefix="ragghost_demo_")
    try:
        _build(d)
        out.write("rag-ghost demo -- a tiny system with four planted problems, examined live\n")
        out.write("=" * 70 + "\n")
        out.write("The system under the microscope:\n"
                  "  reports/exporter.py   built, and nothing imports it\n"
                  "  inventory/sync.py     names inventory.warehouse, which was deleted\n"
                  "  inventory/test_sync.py   a test living outside tests/\n"
                  "  shipping/             real code, no test guards it\n\n")

        g = build_graph(d)
        out.write("GRAPH  -> orphans: %s\n" % sorted(__import__("os").path.basename(o) for o in g.orphans))
        out.write("          dangling: %s\n" % (["%s -> %s" % (a, b) for a, b in g.dangling] or "none"))
        idx = organize(d)
        out.write("ORGANIZE -> misfiled: %s\n" % [__import__("os").path.basename(f) for f, _ in idx.misfiled])
        h = harnesses(d)
        out.write("HARNESS  -> ungated subsystems: %s\n" % sorted(h.ungated))
        p = plan(d)
        out.write("PLAN     -> %d action(s), worst first:\n" % len(p.items))
        for sev, kind, target, action in p.items[:6]:
            out.write("             [%-8s] %s\n" % (kind, action))
        a = analyse(d)
        out.write("ANALYSE  -> %s: %s\n" % ("FAN OUT" if a.fan_out else "ONE PASS", a.reason))
        fx = fix(d, apply=False)
        mech = [x for x in fx.fixes if x.mechanical]
        out.write("FIX (dry run) -> %d mechanical fix(es) it can apply and PROVE, "
                  "%d that need a human\n" % (len(mech), len(fx.fixes) - len(mech)))
        out.write("\nExit codes: 0 clean · 1 found something · 2 could-not-tell (never clean).\n"
                  "Point it at a real system:  python3 -m ragghost graph /path/to/system\n")
        return 0
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
