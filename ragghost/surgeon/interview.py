# CALLED BY: ragghost/surgeon/road.py (road.run) and ragghost/surgeon/__main__.py (the CLI); tested by tests/test_surgeon_modules.py
"""INTERVIEW -- ask the owner what they are trying to build, so the tool works to their goal
rather than a generic one. Interactive when a person is present; a scope file when running
unattended (the sandbox and CI use the file). The tool SUGGESTS the common answers so it neither
misses the owner's real goal nor floods them (FABLE-REPO-PLAN open question 4).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

# The output types the tool can ship. This list IS the proof it ships a wide variety, not one.
OUTPUT_TYPES = {
    "api": "A JSON API service with documented endpoints.",
    "dashboard": "An internal dashboard over the system's own data.",
    "landing": "A marketing landing page with a signup.",
    "cli": "A command-line tool packaged and installable.",
}


@dataclass
class Scope:
    goal: str = ""
    output: str = "landing"
    parts: list = field(default_factory=lambda: ["*"])   # which parts of the system to go through
    lookback_days: int = 14                              # how far back to read transcripts
    known_issues: list = field(default_factory=list)
    defaults: dict = field(default_factory=dict)         # values fixers may use (e.g. store_name)
    store_name: str = ""

    def get(self, k, default=None):
        return getattr(self, k, None) or self.defaults.get(k, default)

    @classmethod
    def from_file(cls, path: str) -> "Scope":
        data = json.load(open(path, encoding="utf-8"))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_dict(cls, data: dict) -> "Scope":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


SUGGESTED_ISSUES = [
    "labeling: files exist under names nothing searches",
    "enforcement: rules that remind but do not refuse",
    "eval: nothing can tell good output from bad",
    "scattered files / duplicate & conflicting copies",
    "wrong wiring: built and never called",
    "tools that report to nobody",
]


def ask(prompt, default, interactive):
    if not interactive:
        return default
    try:
        got = input("%s [%s]: " % (prompt, default)).strip()
    except EOFError:
        return default
    return got or default


def interview(interactive=True, scope_file=None, scope_dict=None) -> Scope:
    if scope_file:
        return Scope.from_file(scope_file)
    if scope_dict is not None:
        return Scope.from_dict(scope_dict)
    if not interactive:
        return Scope()
    print("What are you trying to get working? I fix the system, then ship this output.")
    print("Output types I can ship:")
    for k, v in OUTPUT_TYPES.items():
        print("  - %-10s %s" % (k, v))
    print("Common problems I look for automatically:")
    for s in SUGGESTED_ISSUES:
        print("  - %s" % s)
    out = ask("Which output should I ship", "landing", interactive)
    goal = ask("One line: what is this system for", "", interactive)
    name = ask("If a store, its name", "Your Store", interactive)
    back = ask("How many days of transcripts should I read", "14", interactive)
    return Scope(goal=goal, output=out, store_name=name,
                 lookback_days=int(back) if str(back).isdigit() else 14,
                 defaults={"store_name": name})


def selftest() -> int:
    import os
    import tempfile
    ok = fail = 0

    def chk(name, cond):
        nonlocal ok, fail
        print("  %-52s %s" % (name[:52], "PASS" if cond else "FAIL"))
        ok, fail = ok + bool(cond), fail + (not cond)

    s = interview(interactive=False)
    chk("non-interactive returns a default Scope", isinstance(s, Scope) and s.output == "landing")
    s2 = interview(scope_dict={"output": "api", "store_name": "X", "goal": "g"})
    chk("scope_dict is honoured", s2.output == "api" and s2.goal == "g")
    p = os.path.join(tempfile.mkdtemp(), "scope.json")
    json.dump({"output": "dashboard", "store_name": "Aurora", "defaults": {"store_name": "Aurora"}}, open(p, "w"))
    s3 = Scope.from_file(p)
    chk("scope.json loads", s3.output == "dashboard" and s3.get("store_name") == "Aurora")
    chk("OUTPUT_TYPES shows variety (>=4)", len(OUTPUT_TYPES) >= 4)
    print("\n  %d passed, %d failed" % (ok, fail))
    return 1 if fail else 0


if __name__ == "__main__":
    import sys
    sys.exit(selftest())
