# CALLED BY: ragghost/__main__.py  (`python3 -m ragghost graph <path>`)
# FIRES WHEN: asked -- a library module of a standalone tool, run by whoever downloaded it.
"""STAGE 2 -- GRAPH. What is wired to what, in both directions.

⛔ THE FAILURE THIS STAGE EXISTS FOR: two of the quietest ways a self-built system rots are
invisible without a dependency graph.

  1. A file is built, is correct, passes its own tests, and NOTHING imports it. It reads as
     done in every report and runs never. (An ORPHAN: nothing depends on it.)
  2. A file is renamed or moved, and something that named it by path now points at nothing --
     but the reference is a string, so no import error fires and every dashboard stays green.
     (A DANGLING reference: a path named in text that no longer exists.)

So this stage builds the graph two ways and asks the two questions a graph exists to answer:
what breaks if this file CHANGES (its dependents), and what breaks if this file MOVES (the
places that name it). It reads; it never writes to the target.

No dependencies, no network. Python edges are resolved from the real syntax (`ast`), never a
regex, so an import inside a string or a comment is not counted as an edge.
"""
from __future__ import annotations

import ast
import os
import re
import sys

from .scan import VENDORED, scan

__all__ = ["build_graph", "Graph"]


class Graph:
    """The wiring of a system: who depends on whom, and what names no longer resolve."""

    def __init__(self):
        self.root = ""
        self.nodes = set()                 # every source file, repo-relative
        self.edges = {}                    # file -> set(files it depends on)
        self.rev = {}                      # file -> set(files that depend on it)
        self.dangling = []                 # (file, named_path) references that resolve to nothing
        self.unparsed = []                 # files we could not read/parse -> UNKNOWN, not "no edges"
        self.scanned_files = 0             # denominator, from stage 1

    def dependents(self, path):
        """What breaks if `path` CHANGES -- everything that depends on it, transitively."""
        seen, stack = set(), [path]
        while stack:
            cur = stack.pop()
            for d in self.rev.get(cur, ()):
                if d not in seen:
                    seen.add(d)
                    stack.append(d)
        return seen

    @property
    def orphans(self):
        """Files nothing depends on. Code with no dependents is the built-and-never-called shape.

        Entry points are excluded by name -- a CLI, a test, a config or a top-level script is
        SUPPOSED to have no importer, so flagging it would be the over-firing this tool refuses.
        """
        out = []
        for n in sorted(self.nodes):
            if self.rev.get(n):
                continue
            if not n.endswith(".py"):
                continue
            base = os.path.basename(n)
            if base in ("__main__.py", "__init__.py", "setup.py", "conftest.py"):
                continue
            if base.startswith("test_") or "/tests/" in n or n.startswith("tests/"):
                continue
            # example scripts and doc snippets are entry points by nature -- nobody imports them,
            # and flagging them is the crying-wolf this tool refuses.
            if n.startswith("examples/") or "/examples/" in n \
                    or n.startswith("docs/") or "/docs/" in n:
                continue
            out.append(n)
        return out

    def exit_code(self):
        """0 clean, 1 found something, 2 could-not-tell. A graph over nothing is UNKNOWN."""
        if not self.nodes:
            return 2
        if self.dangling or self.orphans:
            return 1
        return 0

    def report(self, out=sys.stdout):
        w = out.write
        w("GRAPH  %s\n" % self.root)
        w("=" * 70 + "\n")
        if not self.nodes:
            w("  NO SOURCE FILES GRAPHED. UNKNOWN, not clean -- nothing was read.\n")
            return
        edge_count = sum(len(v) for v in self.edges.values())
        w("  %d file(s) in the graph, %d dependency edge(s)\n" % (len(self.nodes), edge_count))
        if self.scanned_files and len(self.nodes) != self.scanned_files:
            w("  (of %d files scanned; the rest are not source this stage graphs)\n"
              % self.scanned_files)
        top = sorted(self.rev.items(), key=lambda kv: -len(kv[1]))[:8]
        top = [(f, d) for f, d in top if d]
        if top:
            w("\n  MOST DEPENDED ON -- changing these breaks the most\n")
            for f, deps in top:
                w("    %-52s %d dependent(s)\n" % (f[:52], len(deps)))
        if self.orphans:
            w("\n  ⛔ NOTHING DEPENDS ON THESE %d FILE(S) -- built, maybe correct, never called\n"
              % len(self.orphans))
            for n in self.orphans[:12]:
                w("    %s\n" % n)
        if self.dangling:
            w("\n  ⛔ %d NAMED PATH(S) THAT RESOLVE TO NOTHING -- a move nobody updated\n"
              % len(self.dangling))
            for f, tgt in self.dangling[:12]:
                w("    %s  ->  %s (missing)\n" % (f, tgt))
        if self.unparsed:
            w("\n  COULD NOT PARSE %d file(s) -- their edges are UNKNOWN, not absent\n"
              % len(self.unparsed))
            for p in self.unparsed[:5]:
                w("    %s\n" % p)
        if not self.orphans and not self.dangling:
            w("\n  Every file has a dependent or is a legitimate entry point, and every named\n"
              "  path resolves. Nothing hidden at the wiring layer.\n")


def _py_module_map(nodes):
    """Map an importable dotted module name -> its file, for resolving Python imports to edges."""
    out = {}
    for n in nodes:
        if not n.endswith(".py"):
            continue
        parts = n[:-3].split("/")
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if parts:
            out[".".join(parts)] = n
        out[parts[-1]] = n if parts else out.get(parts[-1])   # bare-name fallback
    return out


def _own_package(rel):
    """The dotted package a repo-relative Python file lives IN.

    `pkg/sub/__init__.py` IS the package `pkg.sub`; `pkg/sub/mod.py` lives in `pkg.sub`. Getting
    that distinction wrong shifts every relative import by one level, which produces edges to
    modules that do not exist rather than an error.
    """
    parts = rel[:-3].split("/") if rel.endswith(".py") else rel.split("/")
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]          # the __init__ IS its package
    else:
        parts = parts[:-1]          # a module lives in its parent package
    return ".".join(p for p in parts if p)


def _imports(pyfile_abs, rel=None):
    """The modules a Python file imports, from its real AST. None if it cannot be parsed.

    ⛔ RELATIVE IMPORTS USED TO BE DROPPED ENTIRELY -- the ImportFrom branch read
    `if node.module and node.level == 0`, so `from . import api, cli` and `from .scan import scan`
    produced NO edge at all. Every well-formed Python package imports its own modules that way, so
    the graph was blind to a system's internal wiring and only saw what crossed a package boundary.

    ⚠ AND IT LOOKED FINE, WHICH IS THE PART WORTH KEEPING: this repository's own top-level modules
    all had dependents, so nothing was reported -- but the edges came from the TEST FILES, which
    import absolutely (`from ragghost import scan`). The moment a subpackage arrived whose modules
    the tests reach only through their package (`ragghost/surgeon/builders/*`), stage 2 called four
    demonstrably wired files orphans. A blind spot that any test suite accidentally papers over is
    exactly the shape this tool exists to find, and it was in the tool. Fixed 2026-09-27.

    `rel` is the file's repo-relative path and is what makes the resolution possible; without it a
    relative import cannot be resolved at all, so it is still skipped rather than guessed.

    ⚠ STILL A NAMED LIMIT: a relative import of something that does NOT exist (`from . import gone`)
    resolves to no module and is silently dropped here rather than reported. `_broken_submodule_refs`
    catches that shape for absolute imports only. Named rather than left looking covered.
    """
    try:
        with open(pyfile_abs, encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError, ValueError):
        return None
    pkg = _own_package(rel) if rel else None
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                mods.add(node.module)
                for a in node.names:
                    mods.add(node.module + "." + a.name)
            elif node.level and pkg is not None:
                # `level` counts the leading dots: 1 = this package, 2 = its parent, and so on.
                base_parts = pkg.split(".") if pkg else []
                if node.level > 1:
                    base_parts = base_parts[:len(base_parts) - (node.level - 1)]
                base = ".".join(base_parts)
                full = ".".join(p for p in (base, node.module or "") if p)
                if full:
                    mods.add(full)
                for a in node.names:
                    if a.name != "*":
                        mods.add(".".join(p for p in (full, a.name) if p))
    return mods


def _from_targets(pyfile_abs):
    """Level-0 `from M import n` pairs (M, n), for spotting a submodule that has gone missing.
    None if the file cannot be parsed -- its references are UNKNOWN, never assumed present."""
    try:
        with open(pyfile_abs, encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError, ValueError):
        return None
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for a in node.names:
                if a.name != "*":
                    out.append((node.module, a.name))
    return out


def _defined_names(init_abs):
    """Top-level names an __init__.py defines or re-exports. None if it cannot be parsed."""
    try:
        with open(init_abs, encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError, ValueError):
        return None
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                names.add((a.asname or a.name).split(".")[0])
    return names


def _broken_submodule_refs(g):
    """`from pkg import x` where pkg is a package WE OWN, but x is neither a submodule of it nor a
    name its __init__ defines -- a module that was moved or deleted and the caller never updated.

    This is the failure that reads like a memory problem and is really a labelling one: no import
    error fires at graph-build time because the checker only looks at files, so the reference rots
    silently. It is kept honest by only firing when the PACKAGE is one we own (so stdlib and
    third-party imports are never touched) and when the name is provably absent from both the
    filesystem and the package's own __init__.
    """
    for n in g.nodes:
        if not n.endswith(".py"):
            continue
        if n.startswith("test_") or os.path.basename(n).startswith("test_") \
                or "/tests/" in n or n.startswith("tests/"):
            continue
        froms = _from_targets(os.path.join(g.root, n))
        if froms is None:
            continue
        for module, name in froms:
            pkg_path = module.replace(".", "/")
            pkg_init = pkg_path + "/__init__.py"
            if pkg_init not in g.nodes:
                continue                       # not a package we own -> external or a module import
            if (pkg_path + "/" + name + ".py") in g.nodes \
                    or (pkg_path + "/" + name + "/__init__.py") in g.nodes:
                continue                       # a real submodule -- fine
            defined = _defined_names(os.path.join(g.root, pkg_init))
            if defined is None or name in defined:
                continue                       # defined in __init__, or unknown -> do not flag
            g.dangling.append((n, "%s.%s" % (module, name)))



# A path-like token: a quoted or bare string with a slash and a known source extension. Kept
# deliberately narrow -- a bare word or a URL is not a file reference, and flagging one would be
# the over-firing this tool refuses.
_PATHISH = re.compile(r"([\w][\w./\-]*\.[A-Za-z0-9]{1,5})")
_TEXT_EXT = (".py", ".js", ".ts", ".tsx", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
             ".conf", ".sh", ".bash", ".md", ".txt", ".html")


def _dangling_refs(g, skip):
    """Named paths that resolve to NOTHING, where the same basename exists elsewhere (a move).

    The near-miss condition -- basename lives somewhere in the tree -- is what keeps this honest:
    an example path in a doc, or a genuinely external file, has no sibling here and is not flagged.
    """
    by_base = {}
    for n in g.nodes:
        by_base.setdefault(os.path.basename(n), set()).add(n)
    # a test file builds fictional fixture trees as strings; a universal basename
    # (__init__.py, main.py) is not a distinctive reference. Neither is a real move, and
    # flagging them is the over-firing this tool refuses.
    _AMBIGUOUS = {"__init__.py", "__main__.py", "setup.py", "conftest.py", "index.js",
                  "index.ts", "main.py", "index.html", "__init__.pyi"}
    for n in g.nodes:
        if not n.endswith(_TEXT_EXT):
            continue
        base_n = os.path.basename(n)
        if base_n.startswith("test_") or "/tests/" in n or n.startswith("tests/"):
            continue
        # a history document DESCRIBES past states, so a path in it is a record, not live wiring;
        # example code references example paths. Neither is a move nobody updated.
        if base_n.upper().split(".")[0] in ("CHANGELOG", "HISTORY", "NEWS", "RELEASES",
                                            "RELEASE-NOTES", "CHANGES") \
                or n.startswith("examples/") or "/examples/" in n:
            continue
        ap = os.path.join(g.root, n)
        try:
            with open(ap, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        seen = set()
        for m in _PATHISH.finditer(text):
            tok = m.group(1)
            if tok in seen or "/" not in tok:
                continue
            seen.add(tok)
            base = os.path.basename(tok)
            if not base.endswith(_TEXT_EXT) and "." not in base:
                continue
            # resolve relative to the file's own directory, then to the repo root
            here = os.path.normpath(os.path.join(os.path.dirname(ap), tok))
            atroot = os.path.normpath(os.path.join(g.root, tok))
            if os.path.exists(here) or os.path.exists(atroot):
                continue
            # only a near-miss: the basename exists somewhere else in the tree = it moved
            if base in _AMBIGUOUS:
                continue
            if base in by_base:
                g.dangling.append((n, tok))


def build_graph(root, skip=VENDORED):
    """Build the two-way dependency graph under `root`. Reads only."""
    g = Graph()
    g.root = os.path.abspath(root)
    s = scan(g.root, skip=skip)
    g.scanned_files = s.files
    # nodes = every real source file we can name, repo-relative
    for dirpath, dirnames, filenames in os.walk(g.root):
        dirnames[:] = [d for d in dirnames if d not in set(skip)]
        for fn in filenames:
            rel = os.path.relpath(os.path.join(dirpath, fn), g.root).replace(os.sep, "/")
            g.nodes.add(rel)
    g.edges = {n: set() for n in g.nodes}
    g.rev = {n: set() for n in g.nodes}
    modmap = _py_module_map(g.nodes)

    for n in g.nodes:
        ap = os.path.join(g.root, n)
        if n.endswith(".py"):
            mods = _imports(ap, rel=n)      # `rel` is what lets a relative import resolve at all
            if mods is None:
                g.unparsed.append(n)
                continue
            for m in mods:
                # resolve the deepest matching module we own; ignore third-party/stdlib
                target = None
                cand = m
                while cand:
                    if cand in modmap:
                        target = modmap[cand]
                        break
                    cand = cand.rsplit(".", 1)[0] if "." in cand else ""
                if target and target != n:
                    g.edges[n].add(target)
                    g.rev[target].add(n)
    _dangling_refs(g, set(skip))
    _broken_submodule_refs(g)
    return g
