# CALLED BY: ragghost/report.py (check) and ragghost/__main__.py
# FIRES WHEN: asked -- the extension point that lets someone add a check without forking.
"""A plugin is a callable that takes a root path and returns a list of ragghost.report.Finding.
Two ways to add one, so it works whether the tool is pip-installed or run from a clone:

  1. ENTRY POINT (installed): register under the group "ragghost.checks" in your package metadata:
         [project.entry-points."ragghost.checks"]
         mychecks = "yourpkg.mychecks:find_things"
  2. LOCAL (a clone): put a module on sys.path named `ragghost_plugin_*` exposing `CHECKS = [fn, ...]`
     or a `register`-decorated function. Every `ragghost_plugin_*` module is discovered and loaded.

A plugin that raises is reported as a load error and skipped -- one bad plugin never takes the run
down, and never silently makes the tool look clean.
"""
from __future__ import annotations

import importlib
import pkgutil

__all__ = ["register", "registered", "discover", "run_plugins", "load_errors"]

_REGISTRY = []          # callables registered in-process via @register
load_errors = []        # (name, error) for anything that failed to load


def register(fn):
    """Decorator: mark a function as a ragghost check. It takes (root) and returns [Finding]."""
    if fn not in _REGISTRY:
        _REGISTRY.append(fn)
    return fn


def registered():
    return list(_REGISTRY)


def _from_entry_points():
    out = []
    try:
        from importlib.metadata import entry_points
    except Exception:
        return out
    try:
        eps = entry_points()
        group = eps.select(group="ragghost.checks") if hasattr(eps, "select") \
            else eps.get("ragghost.checks", [])
        for ep in group:
            try:
                out.append(ep.load())
            except Exception as exc:  # a bad plugin is reported, never fatal
                load_errors.append((getattr(ep, "name", str(ep)), repr(exc)))
    except Exception as exc:
        load_errors.append(("entry_points", repr(exc)))
    return out


def _from_local_modules():
    out = []
    for mod in list(pkgutil.iter_modules()):
        name = mod.name
        if not name.startswith("ragghost_plugin_"):
            continue
        try:
            m = importlib.import_module(name)
        except Exception as exc:
            load_errors.append((name, repr(exc)))
            continue
        checks = getattr(m, "CHECKS", None)
        if checks:
            out.extend(checks)
    return out


def discover():
    """Every plugin check callable: in-process registrations + entry points + local modules."""
    seen, out = set(), []
    for fn in registered() + _from_entry_points() + _from_local_modules():
        key = getattr(fn, "__qualname__", repr(fn)) + ":" + getattr(fn, "__module__", "")
        if key not in seen:
            seen.add(key)
            out.append(fn)
    return out


def run_plugins(root):
    """Run every discovered plugin against root, collecting findings; a raiser is skipped + logged."""
    findings = []
    for fn in discover():
        try:
            findings.extend(fn(root) or [])
        except Exception as exc:
            load_errors.append((getattr(fn, "__qualname__", repr(fn)), repr(exc)))
    return findings
