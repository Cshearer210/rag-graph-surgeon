"""The surgeon's own memory -- so it works by MECHANISM, not by a session re-reading instructions.

It records, per run: the defect classes it saw, the fix that worked for each, and the output it
shipped. On the next run it can REPLAY a known fix-path for a known defect class (a recorded path
is cheaper and driftless -- FABLE-REPO-PLAN tier rule: a known path is replayed, never re-derived).

Storage is one JSON file, overwritten with STATE (one row per defect class), plus an append-only
events log for history. State, not events, is what a later run reads.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field


@dataclass
class Memory:
    path: str
    state: dict = field(default_factory=dict)     # defect-kind -> {fixer, times, last}

    @classmethod
    def load(cls, path: str) -> "Memory":
        m = cls(path=path)
        if os.path.exists(path):
            try:
                m.state = json.load(open(path, encoding="utf-8")).get("state", {})
            except (json.JSONDecodeError, OSError):
                m.state = {}
        return m

    def record_fix(self, kind: str, fixer: str) -> None:
        row = self.state.setdefault(kind, {"fixer": fixer, "times": 0, "last": ""})
        row["fixer"] = fixer
        row["times"] += 1
        row["last"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    def known_fixer(self, kind: str) -> str | None:
        """A defect class seen 2+ times with the same fix is a KNOWN PATH -- replay it."""
        row = self.state.get(kind)
        return row["fixer"] if row and row["times"] >= 2 else None

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        json.dump({"state": self.state, "saved": time.strftime("%Y-%m-%dT%H:%M:%S")},
                  open(tmp, "w", encoding="utf-8"), indent=2)
        os.replace(tmp, self.path)     # atomic; a torn write never becomes an empty memory


def selftest() -> int:
    import tempfile
    ok = fail = 0

    def chk(name, cond):
        nonlocal ok, fail
        print("  %-52s %s" % (name[:52], "PASS" if cond else "FAIL"))
        ok, fail = ok + bool(cond), fail + (not cond)

    p = os.path.join(tempfile.mkdtemp(), "mem.json")
    m = Memory.load(p)
    chk("fresh memory is empty", m.state == {})
    m.record_fix("broken-json", "fix_trailing_comma")
    chk("one sighting is not yet a known path", m.known_fixer("broken-json") is None)
    m.record_fix("broken-json", "fix_trailing_comma")
    chk("two sightings make it a replayable known path",
        m.known_fixer("broken-json") == "fix_trailing_comma")
    m.save()
    chk("state persists across load (one row per class)",
        Memory.load(p).known_fixer("broken-json") == "fix_trailing_comma")
    chk("state is one row per class, not an append log",
        len(Memory.load(p).state) == 1)
    print("\n  %d passed, %d failed" % (ok, fail))
    return 1 if fail else 0


if __name__ == "__main__":
    import sys
    sys.exit(selftest())
