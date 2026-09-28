# CALLED BY: ragghost/__main__.py  (`python3 -m ragghost harness <path>`)
# FIRES WHEN: asked -- a library module of a standalone tool, run by whoever downloaded it.
"""STAGE 5 -- HARNESS. Split the system into subsystems, each with its doors and its gate.

⛔ THE FAILURE THIS STAGE EXISTS FOR: a subsystem that NOTHING checks. It runs, it is depended on,
and no test or gate guards it -- so when it breaks, nothing says so until something downstream
does, days later. A system with no boundaries is one big blast radius; a system split into
harnesses, each with a gate on its door, fails loudly and locally.

This stage groups the code into harnesses (one per top-level component), finds each harness's
DOORS (the files other harnesses reach into -- its real public surface, from the stage-2 graph),
and asks whether the harness has a GATE (a test that exercises it). A code harness with no gate is
the finding.

No dependencies, no network. It reads; it never writes to the target.
"""
from __future__ import annotations

import ast
import os
import re
import sys

from .graph import build_graph

__all__ = ["harnesses", "Harnesses"]

# A call whose NAME says it checks something. Helper-based assertions (`chk(...)`), context
# managers (`with pytest.raises(...)`, `with pytest.warns(...)`) and a `selftest()` that raises
# on failure are all real assertions.
#
# ⚠ "raise", "warn" AND "selftest" ARE NOT DECORATION. Without them this flagged 30-odd
# perfectly good tests across three real suites -- nearly every one of them a
# `with pytest.raises(...)` case, which is an assertion written as a context manager. Measured
# before this shipped, which is the only reason it is not still wrong.
_CHECKISH = ("assert", "check", "chk", "expect", "verify", "fail", "must", "should",
             "raise", "warn", "selftest")

# A test whose NAME states that the check IS "nothing blew up". This is the author declaring the
# assertion in the one place a reader of the syntax can see it, and it is a real and common
# pattern: 5 of the 6 assertion-free tests found across three live repositories say so here.
_NO_RAISE_NAME = re.compile(r"does_not_(raise|crash|fail|throw)|never_(raises|crashes|fails)"
                            r"|no_(error|crash|exception)", re.I)


def _component(path):
    """The harness a file belongs to: its top-level directory, or '(root)' for a top-level file.

    ⚠ `path` is a GRAPH NODE, which is an identifier, not a filename. `build_graph` normalises every
    node with `.replace(os.sep, "/")` at the one place it creates them (graph.py, the os.walk), so
    the separator here is forward slash on every platform by contract. Splitting on the platform
    separator instead would be the bug: on Windows every node would then be one part and the whole
    stage would collapse into a single `(root)` harness -- silently, with a clean exit code.
    """
    parts = path.split("/")  # path-id: ok -- a graph node, normalised where graph.py creates it
    return parts[0] if len(parts) > 1 else "(root)"


def _call_names(node):
    """Every called name in a subtree, lowercased. A `with pytest.raises(...)` item is a Call
    like any other, so walking the tree finds it without a special case."""
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            out.append((getattr(f, "id", None) or getattr(f, "attr", None) or "").lower())
    return out


def _has_assertion(fn):
    for n in ast.walk(fn):
        if isinstance(n, (ast.Assert, ast.Raise)):
            return True
    return any(any(k in name for k in _CHECKISH) for name in _call_names(fn))


def _dotted(node):
    """`pytest.mark.skip` -> "pytest.mark.skip". Used to tell a real skip from a method named
    `skip` on somebody's own object."""
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.insert(0, cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.insert(0, cur.id)
    return ".".join(parts)


def _always_skipped(fn):
    """A test that never runs, sitting inside a green suite.

    ⚠ `skipif` AND `skipUnless` ARE CONDITIONAL AND LEGITIMATE -- a test that does not run on
    Windows is not a test that never runs. Only an unconditional skip counts.

    ⚠ AND THE RECEIVER MATTERS, which cost two false positives before it was measured: a call to
    a method named `skip` on somebody's own object -- a coverage ledger recording a skipped
    member, say -- is not pytest's skip. Only `pytest.skip`, `self.skipTest`, a bare imported
    `skip`/`skipTest`, and the `skip` decorators count.
    """
    for dec in fn.decorator_list:
        name = _dotted(dec.func if isinstance(dec, ast.Call) else dec)
        if name.rsplit(".", 1)[-1] == "skip":
            return True
    for st in fn.body[:2]:
        if not (isinstance(st, ast.Expr) and isinstance(st.value, ast.Call)):
            continue
        name = _dotted(st.value.func)
        head, last = (name.split(".", 1)[0], name.rsplit(".", 1)[-1])
        if last == "skipTest" and head in ("self", "cls"):
            return True
        if last == "skip" and head in ("pytest", "unittest", "skip"):
            return True
    return False


def _computes_from_literals(node):
    """An expression that COMPUTES a value out of literals alone.

    ⚠ NOT merely "a literal". `[]` and `{"k": 3}` are expected VALUES and comparing a call's
    result against one is a perfectly good assertion -- 8 good tests were flagged before this
    distinction was measured. `2 + 3` re-performs the operation under test, and that is the
    tautology.
    """
    if not isinstance(node, (ast.BinOp, ast.UnaryOp, ast.BoolOp)):
        return False
    return not any(isinstance(n, (ast.Name, ast.Attribute, ast.Call, ast.Subscript))
                   for n in ast.walk(node))


def _swallows_its_failure(fn):
    """A try/except around an assertion whose handler lets the failure through silently.

    ⚠ THE MUST-RAISE TEST IS THE GUARD: `try: f(); assert False; except ValueError: pass` is a
    correct test -- the `assert False` is the failure path and the handler is the SUCCESS path.
    A try body ending in an unconditional failure marker is therefore left alone.
    """
    for n in ast.walk(fn):
        if not isinstance(n, ast.Try):
            continue
        body = ast.Module(body=n.body, type_ignores=[])
        if not any(isinstance(x, ast.Assert) for x in ast.walk(body)):
            continue
        tail = n.body[-1] if n.body else None
        if isinstance(tail, ast.Assert) and isinstance(tail.test, ast.Constant) \
                and not tail.test.value:
            continue                       # the handler is the success path
        for h in n.handlers:
            hb = ast.Module(body=h.body, type_ignores=[])
            if any(isinstance(x, (ast.Raise, ast.Assert)) for x in ast.walk(hb)):
                continue
            if any(any(k in c for k in _CHECKISH) for c in _call_names(hb)):
                continue
            return True
    return False


def hollow_gates(abs_path):
    """The tests in one file that CANNOT FAIL, as (test name, line, shape). None if unparsable.

    ⛔ THE FAILURE THIS EXISTS FOR, and it is this stage's own blind spot: a harness counts as
    GATED when a test exists. A test that cannot fail is green forever, counts as coverage, and
    leaves the subsystem as unguarded as it was before anybody wrote it -- while every report
    says it is gated. That is worse than an ungated harness, because nobody goes looking.

    FOUR SHAPES, each proven in both directions:

        asserts-nothing        it runs code and checks nothing
        asserts-the-language   it re-implements the code it is testing, so it cannot disagree
        swallows-its-failure   a try/except turns any failure green
        always-skipped         it never runs at all
    """
    try:
        with open(abs_path, encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError, ValueError):
        return None
    local_defs = {n.name for n in tree.body
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    out = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not fn.name.startswith("test"):
            continue
        shapes = []
        if _always_skipped(fn):
            shapes.append("always-skipped")
        if not _has_assertion(fn) and not _NO_RAISE_NAME.search(fn.name):
            shapes.append("asserts-nothing")
        if _swallows_its_failure(fn):
            shapes.append("swallows-its-failure")
        for n in ast.walk(fn):
            if isinstance(n, ast.Assert) and isinstance(n.test, ast.Compare):
                left = n.test.left
                local_call = (isinstance(left, ast.Call) and isinstance(left.func, ast.Name)
                              and left.func.id in local_defs)
                if local_call and any(_computes_from_literals(r) for r in n.test.comparators):
                    shapes.append("asserts-the-language")
                    break
        if shapes:
            out.append((fn.name, fn.lineno, sorted(set(shapes))))
    return out


class Harnesses:
    def __init__(self):
        self.root = ""
        self.groups = {}          # harness -> {"files","code","doors","gated","tests"}
        self.ungated = []         # harnesses of code with no gate
        self.hollow_gates = []    # (file, test name, line, [shapes]) -- a test that cannot fail
        self.total_files = 0

    def exit_code(self):
        if not self.groups:
            return 2
        if self.ungated or self.hollow_gates:
            return 1
        return 0

    def report(self, out=sys.stdout):
        w = out.write
        w("HARNESS  %s\n" % self.root)
        w("=" * 70 + "\n")
        if not self.groups:
            w("  NO HARNESSES. UNKNOWN, not clean -- nothing was grouped.\n")
            return
        w("  %d file(s) in %d harness(es)\n" % (self.total_files, len(self.groups)))
        w("\n  EACH HARNESS -- its size, its doors (public surface), and its gate\n")
        for name in sorted(self.groups):
            g = self.groups[name]
            gate = "gate: %s" % ("yes" if g["gated"] else "⛔ NONE")
            w("    %-24s %3d file(s)  %2d door(s)  %s\n"
              % (name[:24], len(g["files"]), len(g["doors"]), gate))
        if self.ungated:
            w("\n  ⛔ %d CODE HARNESS(ES) WITH NO GATE -- nothing tests these\n" % len(self.ungated))
            for name in self.ungated:
                w("    %s  (%d file(s))\n" % (name, len(self.groups[name]["files"])))
            w("\n  A subsystem no test guards fails silently. Add a gate before trusting it.\n")
        if self.hollow_gates:
            w("\n  ⛔ %d TEST(S) THAT CANNOT FAIL -- green forever, counted as coverage\n"
              % len(self.hollow_gates))
            for f, name, line, shapes in self.hollow_gates[:12]:
                w("    %-40s %s:%d\n" % (name[:40], f, line))
                w("        %s\n" % ", ".join(shapes))
        if not self.ungated and not self.hollow_gates:
            w("\n  Every code harness has a gate, and every test in them can fail.\n")


def harnesses(root):
    """Group the system into harnesses and find the ungated ones. Reads only."""
    h = Harnesses()
    g = build_graph(root)
    h.root = g.root
    h.total_files = len(g.nodes)
    for n in g.nodes:
        comp = _component(n)
        grp = h.groups.setdefault(comp, {"files": set(), "code": set(), "doors": set(),
                                          "gated": False, "tests": set()})
        grp["files"].add(n)
        base = os.path.basename(n)
        is_test = base.startswith("test_") or "/tests/" in n or n.startswith("tests/")
        if is_test:
            grp["tests"].add(n)
        elif n.endswith(".py"):
            grp["code"].add(n)
    # doors: a file reached by an edge from OUTSIDE its own harness
    for src, targets in g.edges.items():
        for tgt in targets:
            if _component(src) != _component(tgt):
                h.groups[_component(tgt)]["doors"].add(tgt)
    # ⛔ A TEST THAT CANNOT FAIL IS NOT A GATE, and until this was added a file full of them
    # counted as one. Find them first, so "gated" can mean what it says.
    cannot_fail = {}                       # test file -> number of tests that cannot fail
    test_counts = {}                       # test file -> number of test functions
    for n in sorted(g.nodes):
        if not n.endswith(".py"):
            continue
        base = os.path.basename(n)
        if not (base.startswith("test_") or "/tests/" in ("/" + n) or n.startswith("tests/")):
            continue
        got = hollow_gates(os.path.join(g.root, n))
        if got is None:
            continue                       # unparsable -> UNKNOWN, never "its tests are fine"
        try:
            with open(os.path.join(g.root, n), encoding="utf-8", errors="replace") as f:
                tree = ast.parse(f.read())
            test_counts[n] = sum(1 for x in ast.walk(tree)
                                 if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
                                 and x.name.startswith("test"))
        except (OSError, SyntaxError, ValueError):
            continue
        cannot_fail[n] = len(got)
        for tname, line, shapes in got:
            h.hollow_gates.append((n, tname, line, shapes))

    # a harness is gated if it has its own tests, OR a test anywhere imports one of its files --
    # and a test file whose EVERY test cannot fail does not count as a gate for either.
    #
    # ⚠ `c == 0` IS NOT A REDUNDANT CASE AND LEAVING IT OUT BROKE THREE EXISTING FIXTURES. A file
    # with NO test functions is not a file whose every test is hollow -- it is a helper, a
    # fixture module or an import-only smoke file, and it has always counted as a gate. Only a
    # file that HAS tests, all of which cannot fail, loses that standing.
    real_tests = {n for n, c in test_counts.items()
                  if c == 0 or c > cannot_fail.get(n, 0)}
    tested_files = set()
    for src, targets in g.edges.items():
        base = os.path.basename(src)
        if base.startswith("test_") or "/tests/" in src or src.startswith("tests/"):
            if src in test_counts and src not in real_tests:
                continue                   # every test in it cannot fail: not a gate
            tested_files |= targets
    for name, grp in h.groups.items():
        own_real = {t for t in grp["tests"] if t not in test_counts or t in real_tests}
        grp["gated"] = bool(own_real) or bool(grp["code"] & tested_files)
        if grp["code"] and not grp["gated"]:
            h.ungated.append(name)
    h.ungated.sort()
    return h
