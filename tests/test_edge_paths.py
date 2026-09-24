# CALLED BY: pytest -- the rarely-hit error branches that need a little setup to reach.
# FIRES WHEN: asked.
"""Local plugin discovery, and the read-error paths in retrieve/report that only fire when the
filesystem misbehaves mid-run. Each is a real contract: a bad file is skipped, never fatal."""
import importlib
import sys


from ragghost import plugins
from ragghost.report import Finding, _suppressed_inline
from ragghost.retrieve import build_index


# ── plugins._from_local_modules discovers a ragghost_plugin_* module on sys.path ──
def test_local_module_plugin_is_discovered(tmp_path, monkeypatch):
    mod_dir = tmp_path / "plugdir"
    mod_dir.mkdir()
    (mod_dir / "ragghost_plugin_demo.py").write_text(
        "from ragghost.report import Finding\n"
        "def _c(root):\n"
        "    return [Finding('LOCAL-PLUGIN', 'LOW', 'from a local module', 'd', 'a.py')]\n"
        "CHECKS = [_c]\n"
    )
    monkeypatch.syspath_prepend(str(mod_dir))
    importlib.invalidate_caches()
    saved = list(plugins._REGISTRY)
    plugins._REGISTRY.clear()
    try:
        found = plugins._from_local_modules()
        assert any(getattr(fn, "__name__", "") == "_c" for fn in found)
    finally:
        plugins._REGISTRY[:] = saved
        sys.modules.pop("ragghost_plugin_demo", None)


def test_local_module_that_raises_on_import_is_logged(tmp_path, monkeypatch):
    mod_dir = tmp_path / "plugdir2"
    mod_dir.mkdir()
    (mod_dir / "ragghost_plugin_boom.py").write_text("raise RuntimeError('bad plugin')\n")
    monkeypatch.syspath_prepend(str(mod_dir))
    importlib.invalidate_caches()
    saved_err = list(plugins.load_errors)
    plugins.load_errors.clear()
    try:
        plugins._from_local_modules()
        assert any("ragghost_plugin_boom" in name for name, _ in plugins.load_errors)
    finally:
        plugins.load_errors[:] = saved_err
        sys.modules.pop("ragghost_plugin_boom", None)


# ── retrieve tolerates a file that cannot be read while indexing ─────────────
def test_unreadable_file_is_counted_not_indexed(tree, monkeypatch):
    d = tree({"good.md": "readable content here\n", "bad.md": "will fail to open\n"})
    real_open = open

    def flaky_open(path, *a, **k):
        if str(path).endswith("bad.md"):
            raise OSError("cannot read")
        return real_open(path, *a, **k)

    monkeypatch.setattr("builtins.open", flaky_open)
    r = build_index(d)
    assert "good.md" in r.docs
    assert "bad.md" not in r.docs
    assert r.unreadable >= 1


# ── report suppression tolerates a file it cannot open ──────────────────────
def test_suppression_open_error_is_not_suppressed(tree, monkeypatch):
    d = tree({"a.py": "X = 1\n"})
    real_open = open

    def flaky_open(path, *a, **k):
        if str(path).endswith("a.py"):
            raise OSError("cannot read")
        return real_open(path, *a, **k)

    monkeypatch.setattr("builtins.open", flaky_open)
    f = Finding("GRAPH-ORPHAN", "MEDIUM", "m", "d", "a.py")
    # an unreadable file cannot carry a suppression comment -> it is NOT suppressed
    assert _suppressed_inline(f, d) is False
