"""The indexer -- exact, deterministic, and (for the questions it answers) better than RAG.

WHY NOT EMBEDDINGS HERE: to find WHERE a symbol is defined, WHO imports a module, or WHICH files
mention a name, an exact index beats a semantic one every time -- it never hallucinates a match and
it costs nothing. Semantic retrieval is a SEPARATE, pluggable layer (see agents.SemanticIndex) for
the one question exactness cannot answer: "is this the same idea as that". This module is the
exact half, and it is the half the repair pipeline leans on.

It buckets every file by KIND and builds three maps: name->files, import->files, and a per-file
summary. Population is DISCOVERED by walking, never typed.
"""
from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field

CODE = {".py"}
WEB = {".html", ".css", ".js", ".mjs", ".jsx", ".ts", ".tsx"}
DATA = {".json", ".yaml", ".yml", ".toml", ".csv", ".sql", ".env"}
DOC = {".md", ".rst", ".txt"}
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
             ".next", ".wrangler", ".pytest_cache", ".mypy_cache"}


def bucket(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in CODE:
        return "code"
    if ext in WEB:
        return "web"
    if ext in DATA:
        return "data"
    if ext in DOC:
        return "doc"
    return "other"


@dataclass
class Index:
    root: str
    files: list = field(default_factory=list)             # relpaths
    buckets: dict = field(default_factory=dict)           # kind -> [relpath]
    defines: dict = field(default_factory=dict)           # symbol -> [relpath]  (python defs)
    imports: dict = field(default_factory=dict)           # module -> [relpath]  (who imports it)
    mentions: dict = field(default_factory=dict)          # token -> set(relpath) (lowercased words)

    def where_defined(self, symbol: str) -> list:
        return sorted(self.defines.get(symbol, []))

    def who_imports(self, module: str) -> list:
        return sorted(self.imports.get(module, []))

    def find(self, token: str) -> list:
        return sorted(self.mentions.get(token.lower(), set()))

    def summary(self) -> dict:
        return {"files": len(self.files),
                "by_kind": {k: len(v) for k, v in sorted(self.buckets.items())},
                "python_symbols": len(self.defines),
                "duplicate_symbols": sum(1 for v in self.defines.values() if len(v) > 1)}


_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


def build(root: str, max_bytes: int = 400_000) -> Index:
    root = os.path.abspath(root)
    idx = Index(root=root)
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS and not d.startswith(".")]
        for f in fn:
            if f.startswith("."):
                continue
            full = os.path.join(dp, f)
            rel = os.path.relpath(full, root)
            idx.files.append(rel)
            k = bucket(rel)
            idx.buckets.setdefault(k, []).append(rel)
            try:
                if os.path.getsize(full) > max_bytes:
                    continue
                text = open(full, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            for w in set(m.group(0).lower() for m in _WORD.finditer(text)):
                idx.mentions.setdefault(w, set()).add(rel)
            if k == "code" and rel.endswith(".py"):
                _index_python(text, rel, idx)
    return idx


def _index_python(text: str, rel: str, idx: Index) -> None:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            idx.defines.setdefault(node.name, []).append(rel)
        elif isinstance(node, ast.Import):
            for a in node.names:
                idx.imports.setdefault(a.name.split(".")[0], []).append(rel)
        elif isinstance(node, ast.ImportFrom) and node.module:
            idx.imports.setdefault(node.module.split(".")[0], []).append(rel)


def selftest() -> int:
    import tempfile
    ok = fail = 0

    def chk(name, cond):
        nonlocal ok, fail
        print("  %-52s %s" % (name[:52], "PASS" if cond else "FAIL"))
        ok, fail = ok + bool(cond), fail + (not cond)

    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "pkg"))
    open(os.path.join(d, "pkg", "a.py"), "w").write("import os\ndef helper():\n    return 1\n")
    open(os.path.join(d, "pkg", "b.py"), "w").write("from pkg import a\ndef helper():\n    return 2\n")
    open(os.path.join(d, "index.html"), "w").write("<h1>store</h1>")
    open(os.path.join(d, "data.json"), "w").write("{}")
    os.makedirs(os.path.join(d, "node_modules"))
    open(os.path.join(d, "node_modules", "junk.py"), "w").write("def should_not_be_indexed(): pass")

    idx = build(d)
    chk("walks files, skips node_modules", "should_not_be_indexed" not in idx.defines)
    chk("buckets code/web/data", idx.buckets.get("code") and idx.buckets.get("web") and idx.buckets.get("data"))
    chk("finds a duplicate symbol (helper in 2 files)", len(idx.where_defined("helper")) == 2)
    chk("who_imports resolves", any("b.py" in p for p in idx.who_imports("pkg")))
    chk("exact find by token", any("index.html" in p for p in idx.find("store")))
    chk("summary reports duplicate_symbols>=1", idx.summary()["duplicate_symbols"] >= 1)
    print("\n  %d passed, %d failed" % (ok, fail))
    return 1 if fail else 0


if __name__ == "__main__":
    import sys
    sys.exit(selftest())
