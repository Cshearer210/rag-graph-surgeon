"""The dependency graph: what calls / imports what, so orphans and broken wiring are visible.

Every edge is MARKED by how it was learned (FABLE-REPO-PLAN law 4: a guessed edge is marked as
guessed):
    EXTRACTED  read straight from the AST (an `import`/`from` in the source)      -- certain
    INFERRED   a filename referenced in a string, a template include              -- probable
    AMBIGUOUS  a dynamic/wildcard reference a static read cannot resolve          -- a maybe

An ORPHAN is a code file with no inbound EXTRACTED edge and that is not an entrypoint. It is a
CANDIDATE for "built and never wired", never an automatic deletion -- the graph proposes, the owner
disposes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

EXTRACTED, INFERRED, AMBIGUOUS = "EXTRACTED", "INFERRED", "AMBIGUOUS"

# a file is an entrypoint (legitimately having no importer) if it looks like one
ENTRYPOINT_HINTS = ("cli.py", "__main__.py", "main.py", "manage.py", "app.py", "wsgi.py",
                    "conftest.py", "setup.py")


@dataclass
class Graph:
    edges: list = field(default_factory=list)     # (src_relpath, dst_module, how)
    module_of: dict = field(default_factory=dict)  # top-level module name -> relpath

    def inbound(self, module: str) -> list:
        return [e for e in self.edges if e[1] == module]


def _module_name(rel: str) -> str:
    base = os.path.basename(rel)
    if base == "__init__.py":
        return os.path.basename(os.path.dirname(rel)) or rel
    return base[:-3] if base.endswith(".py") else base


def build(index) -> Graph:
    g = Graph()
    code = index.buckets.get("code", [])
    for rel in code:
        g.module_of[_module_name(rel)] = rel
    # EXTRACTED edges from the index's import map
    for module, importers in index.imports.items():
        for imp in importers:
            g.edges.append((imp, module, EXTRACTED))
    # INFERRED edges: a code/web file names another local file in a string/include
    localnames = {os.path.basename(r): r for r in index.files}
    for rel in code + index.buckets.get("web", []):
        for other_base, other_rel in localnames.items():
            if other_rel == rel:
                continue
            if other_base in _tokens(index, rel) and other_base.rsplit(".", 1)[0] not in ("index",):
                g.edges.append((rel, _module_name(other_rel), INFERRED))
    return g


def _tokens(index, rel):
    # cheap reverse lookup: which tokens does this file mention (from the index)
    out = set()
    for tok, files in index.mentions.items():
        if rel in files:
            out.add(tok)
    return out


def orphans(index, g: Graph) -> list:
    """Code files nothing imports (EXTRACTED) and that are not entrypoints -> unwired candidates."""
    imported_modules = {e[1] for e in g.edges if e[2] == EXTRACTED}
    out = []
    for rel in index.buckets.get("code", []):
        mod = _module_name(rel)
        base = os.path.basename(rel)
        if base in ENTRYPOINT_HINTS or base.startswith("test_") or base == "__init__.py":
            continue
        if mod not in imported_modules:
            out.append(rel)
    return sorted(out)


def selftest() -> int:
    import tempfile
    from . import index as index_mod
    ok = fail = 0

    def chk(name, cond):
        nonlocal ok, fail
        print("  %-52s %s" % (name[:52], "PASS" if cond else "FAIL"))
        ok, fail = ok + bool(cond), fail + (not cond)

    d = tempfile.mkdtemp()
    open(os.path.join(d, "used.py"), "w").write("def f():\n    return 1\n")
    open(os.path.join(d, "main.py"), "w").write("import used\nused.f()\n")
    open(os.path.join(d, "orphan.py"), "w").write("def never_called():\n    return 2\n")
    idx = index_mod.build(d)
    g = build(idx)
    chk("EXTRACTED edge main->used exists",
        any(e for e in g.edges if e[1] == "used" and e[2] == EXTRACTED))
    orp = orphans(idx, g)
    chk("orphan.py flagged as unwired", any("orphan.py" in o for o in orp))
    chk("main.py NOT flagged (entrypoint)", not any("main.py" in o for o in orp))
    chk("used.py NOT flagged (it is imported)", not any(o == "used.py" for o in orp))
    chk("every edge carries a how-marker",
        all(e[2] in (EXTRACTED, INFERRED, AMBIGUOUS) for e in g.edges))
    print("\n  %d passed, %d failed" % (ok, fail))
    return 1 if fail else 0


if __name__ == "__main__":
    import sys
    sys.exit(selftest())
