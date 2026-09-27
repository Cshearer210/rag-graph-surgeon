"""Scanners that find what is broken. Each returns Diagnosis objects; each Diagnosis names the
FIXER that can resolve it (or None -> it must be surfaced to the owner).

A Diagnosis is EVIDENCE, not an opinion: it carries the file, the exact problem, and -- where a
fix exists -- enough to apply it deterministically. Nothing here calls a model.
"""
from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass, field

from . import graph as graph_mod


@dataclass
class Diagnosis:
    kind: str                 # broken-json | broken-import | syntax-error | missing-config-field | unwired | dead-path-ref
    file: str                 # relpath in the target/workspace
    detail: str
    fixer: str | None = None  # name of a fix.py fixer, or None -> surface to owner
    data: dict = field(default_factory=dict)   # everything the fixer needs

    def __str__(self):
        tag = "fixable" if self.fixer else "SURFACE"
        return "[%s] %-18s %-24s %s" % (tag, self.kind, self.file[:24], self.detail[:60])


def _read(root, rel):
    return open(os.path.join(root, rel), encoding="utf-8", errors="replace").read()


def broken_json(root, index) -> list:
    out = []
    for rel in index.buckets.get("data", []):
        if not rel.endswith(".json"):
            continue
        try:
            txt = _read(root, rel)
        except OSError:
            continue
        if not txt.strip():
            out.append(Diagnosis("broken-json", rel, "file is empty (invalid JSON)",
                                 "fix_empty_json", {"empty": True}))
            continue
        try:
            json.loads(txt)
        except json.JSONDecodeError as e:
            # a trailing comma before ] or } is the most common, and deterministically fixable
            if re.search(r",\s*[\]}]", txt):
                out.append(Diagnosis("broken-json", rel, "trailing comma: %s" % e.msg,
                                     "fix_trailing_comma", {}))
            else:
                out.append(Diagnosis("broken-json", rel, "invalid JSON: %s" % e.msg, None))
    return out


def syntax_errors(root, index) -> list:
    out = []
    for rel in index.buckets.get("code", []):
        try:
            compile(_read(root, rel), rel, "exec")
        except SyntaxError as e:
            out.append(Diagnosis("syntax-error", rel, "%s at line %s" % (e.msg, e.lineno), None))
        except OSError:
            continue
    return out


def broken_imports(root, index) -> list:
    """A `from X import ...` / `import X` where X looks LOCAL (a sibling module) but no such module
    exists -- usually a typo. Fixable when exactly one existing local module is a near-match."""
    out = []
    localmods = {os.path.splitext(os.path.basename(r))[0] for r in index.buckets.get("code", [])}
    for rel in index.buckets.get("code", []):
        try:
            tree = ast.parse(_read(root, rel))
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module.split(".")[0]]
            elif isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            for name in names:
                if name in localmods or _is_stdlib_or_installed(name):
                    continue
                near = _near(name, localmods)
                # SURFACE, never auto-rewrite. A name absent from THIS tree may still resolve at
                # runtime via PYTHONPATH or a sibling package (measured 2026-09-22: real modules
                # session_ledger/hook_pipeline were rewritten to wrong fuzzy matches because the
                # scan ran on an isolated copy). An import rewrite is destructive, so it joins the
                # deletion/public/money class the surgeon surfaces for the owner rather than fixing.
                hint = (" (nearest local name: '%s')" % near) if near else ""
                out.append(Diagnosis("broken-import", rel,
                                     "imports '%s' which is not a local module in this tree%s -- "
                                     "NOT auto-fixed; it may resolve at runtime, so confirm before renaming"
                                     % (name, hint),
                                     None, {"wrong": name, "near": near}))
    return out


_CFG_SKIP = {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}


def _locate(root, rel):
    """Find the config the builder needs. Prefer the exact relpath; else the same basename
    anywhere in the tree (a store's config.json commonly lives under data/, not the root).
    Returns the relpath that actually exists, or None."""
    if os.path.exists(os.path.join(root, rel)):
        return rel
    base = os.path.basename(rel)
    best, best_depth = None, 1 << 30
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in _CFG_SKIP and not d.startswith(".")]
        if base in fn:
            found = os.path.relpath(os.path.join(dp, base), root)
            depth = found.count(os.sep)
            if depth < best_depth:
                best, best_depth = found, depth
    return best


def missing_config_field(root, index, required: dict) -> list:
    """required = {relpath: [field, ...]}. A config missing a required key the builder needs.
    The relpath is matched by basename if the exact path is not present, so a config nested under
    data/ is still checked -- and the REAL path is recorded so the fixer edits the right file."""
    out = []
    for rel, fields in required.items():
        found = _locate(root, rel)
        if not found:
            continue
        try:
            data = json.loads(_read(root, found))
        except (json.JSONDecodeError, OSError):
            continue                       # broken_json already owns this
        if not isinstance(data, dict):
            continue
        for f in fields:
            if f not in data:
                out.append(Diagnosis("missing-config-field", found,
                                     "missing required field '%s'" % f,
                                     "fix_add_config_field", {"field": f}))
    return out


def unwired(root, index) -> list:
    g = graph_mod.build(index)
    return [Diagnosis("unwired", rel, "nothing imports this module (built and never wired)", None)
            for rel in graph_mod.orphans(index, g)]


_STDLIB = set("os sys re json math time datetime pathlib typing collections itertools functools "
              "subprocess argparse dataclasses io ast glob shutil tempfile unittest hashlib "
              "random string textwrap urllib http logging enum abc contextlib".split())


def _is_stdlib_or_installed(name: str) -> bool:
    if name in _STDLIB:
        return True
    try:
        import importlib.util
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def _near(name: str, candidates: set) -> str | None:
    """Nearest candidate by edit-distance-ish: shares a long common prefix or is 1-2 edits away."""
    best, bestscore = None, 0.0
    for c in candidates:
        s = _ratio(name, c)
        if s > bestscore:
            best, bestscore = c, s
    return best if bestscore >= 0.7 else None


def _ratio(a: str, b: str) -> float:
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio()


_PATHLIKE = re.compile(r"^[\w./\-]+\.(py|json|js|ts|jsx|tsx|html|css|md|txt|csv|yml|yaml|png|jpg|jpeg|svg|toml|ini)$", re.I)


def _looks_like_path(s: str) -> bool:
    return bool(_PATHLIKE.match(s.strip())) and " " not in s.strip()


def _basename_map(root):
    m = {}
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in _CFG_SKIP and not d.startswith(".")]
        for f in fn:
            m.setdefault(f, []).append(os.path.relpath(os.path.join(dp, f), root))
    return m


def dead_path_reference(root, index) -> list:
    """A config value that names a file which does not exist. If exactly one file with that
    basename exists elsewhere, it was renamed/moved -> repoint it (safe, deterministic). If zero
    or several match, it is the owner's call -> SURFACE. Matches Chris's own example: 'an import
    points at a file that was renamed'. Only top-level string values are considered, so the fix is
    unambiguous."""
    out = []
    bmap = None
    for rel in index.buckets.get("data", []):
        if not rel.endswith(".json"):
            continue
        try:
            data = json.loads(_read(root, rel))
        except (json.JSONDecodeError, OSError):
            continue                       # broken_json owns malformed files
        if not isinstance(data, dict):
            continue
        for key, val in data.items():
            if not isinstance(val, str) or not _looks_like_path(val):
                continue
            if os.path.exists(os.path.join(root, val)):
                continue                   # the reference resolves -- fine
            if bmap is None:
                bmap = _basename_map(root)
            matches = [m for m in bmap.get(os.path.basename(val), []) if m != val]
            if len(matches) == 1:
                out.append(Diagnosis("dead-path-ref", rel,
                                     "'%s' points at '%s' which is gone; found it at '%s'"
                                     % (key, val, matches[0]),
                                     "fix_repoint_path", {"key": key, "old": val, "new": matches[0]}))
            else:
                out.append(Diagnosis("dead-path-ref", rel,
                                     "'%s' points at '%s' which is gone (%d candidates -- owner decides)"
                                     % (key, val, len(matches)), None, {"key": key, "old": val}))
    return out


def run_all(root, index, required_fields: dict | None = None) -> list:
    ds = []
    ds += broken_json(root, index)
    ds += syntax_errors(root, index)
    ds += broken_imports(root, index)
    ds += unwired(root, index)
    ds += dead_path_reference(root, index)
    if required_fields:
        ds += missing_config_field(root, index, required_fields)
    return ds


def selftest() -> int:
    import tempfile
    from . import index as index_mod
    ok = fail = 0

    def chk(name, cond):
        nonlocal ok, fail
        print("  %-54s %s" % (name[:54], "PASS" if cond else "FAIL"))
        ok, fail = ok + bool(cond), fail + (not cond)

    d = tempfile.mkdtemp()
    open(os.path.join(d, "products.json"), "w").write('[{"name":"a"},{"name":"b"},]')  # trailing comma
    open(os.path.join(d, "empty.json"), "w").write("")
    # config: missing store_name; "engine" points at a file that was moved to src/; "readme" resolves; "currency" is not a path
    os.makedirs(os.path.join(d, "src"), exist_ok=True)
    open(os.path.join(d, "src", "renderer.py"), "w").write("def go():\n    return 1\n")
    open(os.path.join(d, "config.json"), "w").write(
        '{"currency":"USD","engine":"renderer.py","readme":"template.py"}')
    open(os.path.join(d, "template.py"), "w").write("def render(x):\n    return x\n")
    open(os.path.join(d, "build.py"), "w").write("from templating import render\nrender(1)\n")  # typo
    open(os.path.join(d, "bad.py"), "w").write("def broken(:\n    pass\n")              # syntax error
    open(os.path.join(d, "orphan_helper.py"), "w").write("def unused():\n    return 9\n")
    idx = index_mod.build(d)
    ds = run_all(d, idx, {"config.json": ["store_name"]})
    kinds = {x.kind for x in ds}
    chk("finds trailing-comma json (fixable)",
        any(x.kind == "broken-json" and x.fixer == "fix_trailing_comma" for x in ds))
    chk("finds empty json (fixable)",
        any(x.kind == "broken-json" and x.fixer == "fix_empty_json" for x in ds))
    chk("surfaces a broken import (NOT auto-rewritten -- it may resolve at runtime)",
        any(x.kind == "broken-import" and x.fixer is None and x.data.get("near") == "template" for x in ds))
    chk("finds syntax error (surfaced, no fixer)",
        any(x.kind == "syntax-error" and x.fixer is None for x in ds))
    chk("finds missing config field (fixable)",
        any(x.kind == "missing-config-field" and x.data.get("field") == "store_name" for x in ds))
    chk("finds unwired orphan (surfaced)",
        any(x.kind == "unwired" and "orphan_helper.py" in x.file for x in ds))
    chk("does NOT flag stdlib/installed imports as broken",
        not any(x.kind == "broken-import" and x.data.get("wrong") == "os" for x in ds))
    chk("finds a config path pointing at a renamed file (fixable, unique match)",
        any(x.kind == "dead-path-ref" and x.fixer == "fix_repoint_path"
            and x.data.get("new", "").endswith("renderer.py") for x in ds))
    chk("does NOT flag a config path that still resolves (readme->template.py)",
        not any(x.kind == "dead-path-ref" and x.data.get("old") == "template.py" for x in ds))
    chk("does NOT flag a non-path config value (currency USD)",
        not any(x.kind == "dead-path-ref" and x.data.get("old") == "USD" for x in ds))
    print("\n  %d passed, %d failed" % (ok, fail))
    return 1 if fail else 0


if __name__ == "__main__":
    import sys
    sys.exit(selftest())
