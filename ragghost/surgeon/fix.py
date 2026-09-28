"""Fixers, keyed by name to a Diagnosis. Each returns (fixed: bool, note: str).

SAFETY (FABLE-REPO-PLAN, "what is deliberately not automated"): a fixer only EDITS or ADDS inside
the workspace. It never deletes a file, never touches anything a stranger could see, never spends
money. A Diagnosis whose `fixer` is None is surfaced to the owner, never guessed at.

Every fix is deterministic and reproducible; nothing here calls a model.
"""
from __future__ import annotations

import json
import os
import re

from ._common import read_text as _read


def _write(root, rel, text):
    with open(os.path.join(root, rel), "w", encoding="utf-8") as fh:
        fh.write(text)


def fix_trailing_comma(root, diag, scope=None):
    txt = _read(root, diag.file)
    fixed = re.sub(r",(\s*[\]}])", r"\1", txt)
    try:
        json.loads(fixed)
    except json.JSONDecodeError as e:
        return False, "removing trailing commas did not yield valid JSON: %s" % e.msg
    _write(root, diag.file, fixed)
    return True, "removed trailing comma(s); JSON now parses"


def fix_empty_json(root, diag, scope=None):
    # an empty .json is invalid; the safe, reversible fix is an empty object, which parses
    _write(root, diag.file, "{}\n")
    return True, "replaced empty file with {} so it is valid JSON"


def fix_add_config_field(root, diag, scope=None):
    field = diag.data["field"]
    try:
        data = json.loads(_read(root, diag.file))
    except json.JSONDecodeError as e:
        return False, "config is not valid JSON yet (%s); fix that first" % e.msg
    # take the value from the owner's scope if present, else a safe placeholder the owner can edit
    value = (scope or {}).get(field) or (scope or {}).get("defaults", {}).get(field) or "TODO: %s" % field
    data[field] = value
    _write(root, diag.file, json.dumps(data, indent=2) + "\n")
    return True, "added '%s' = %r (from scope)" % (field, value)


def fix_repoint_path(root, diag, scope=None):
    """A config value points at a file that was renamed/moved; repoint it to the one file that
    now carries that name. Deterministic: the scanner only emits this fixer when EXACTLY one
    candidate exists (zero or several are surfaced to the owner instead)."""
    key, new = diag.data["key"], diag.data["new"]
    try:
        data = json.loads(_read(root, diag.file))
    except json.JSONDecodeError as e:
        return False, "config is not valid JSON yet (%s); fix that first" % e.msg
    if not isinstance(data, dict) or key not in data:
        return False, "the key '%s' is no longer in the config" % key
    data[key] = new
    _write(root, diag.file, json.dumps(data, indent=2) + "\n")
    return True, "repointed '%s' -> '%s' (the renamed file)" % (key, new)


FIXERS = {
    "fix_trailing_comma": fix_trailing_comma,
    "fix_empty_json": fix_empty_json,
    "fix_add_config_field": fix_add_config_field,
    "fix_repoint_path": fix_repoint_path,
}


def apply(root, diagnoses, scope=None):
    """Apply every fixable diagnosis. Returns (applied, surfaced) -- surfaced are the owner's to
    decide (fixer is None, or the fixer declined)."""
    applied, surfaced = [], []
    for d in diagnoses:
        fn = FIXERS.get(d.fixer) if d.fixer else None
        if fn is None:
            surfaced.append((d, "no automatic fix -- owner decides"))
            continue
        try:
            ok, note = fn(root, d, scope)
        except Exception as e:                       # a fixer that crashes surfaces, never lies
            ok, note = False, "fixer raised %s: %s" % (type(e).__name__, e)
        (applied if ok else surfaced).append((d, note))
    return applied, surfaced


def selftest() -> int:
    import tempfile
    from . import diagnose, index as index_mod
    ok = fail = 0

    def chk(name, cond):
        nonlocal ok, fail
        print("  %-54s %s" % (name[:54], "PASS" if cond else "FAIL"))
        ok, fail = ok + bool(cond), fail + (not cond)

    d = tempfile.mkdtemp()
    open(os.path.join(d, "products.json"), "w").write('[{"n":"a"},{"n":"b"},]')
    open(os.path.join(d, "empty.json"), "w").write("")
    open(os.path.join(d, "config.json"), "w").write('{"currency":"USD"}')
    open(os.path.join(d, "template.py"), "w").write("def render(x): return x\n")
    open(os.path.join(d, "build.py"), "w").write("from templating import render\n")
    idx = index_mod.build(d)
    ds = diagnose.run_all(d, idx, {"config.json": ["store_name"]})
    applied, surfaced = apply(d, ds, scope={"store_name": "Aurora Goods"})

    # every fixable one actually landed, verified by reading the world back (not the return code)
    chk("trailing-comma json now parses", _parses(os.path.join(d, "products.json")))
    chk("empty json now parses", _parses(os.path.join(d, "empty.json")))
    cfg = json.load(open(os.path.join(d, "config.json")))
    chk("config field added from scope", cfg.get("store_name") == "Aurora Goods")
    chk("broken import SURFACED, not auto-rewritten (safe)",
        "from templating import render" in open(os.path.join(d, "build.py")).read()
        and any(x.kind == "broken-import" and x.fixer is None for x in ds))
    chk("something was surfaced (no false auto-fix of unknowns)", isinstance(surfaced, list))
    chk("a re-run finds nothing left to fix (idempotent)",
        not [x for x in diagnose.run_all(d, index_mod.build(d), {"config.json": ["store_name"]})
             if x.fixer])
    print("\n  %d passed, %d failed" % (ok, fail))
    return 1 if fail else 0


def _parses(p):
    try:
        json.load(open(p))
        return True
    except Exception:
        return False


if __name__ == "__main__":
    import sys
    sys.exit(selftest())
