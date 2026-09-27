# CALLED BY: ragghost/cli.py  (`python3 -m ragghost scan <path>`)
# FIRES WHEN: asked -- this is a library module of a standalone tool, and the tool is run by the
#             person who downloaded it. There is no hook chain in a stranger's checkout.
"""STAGE 1 -- SCAN. What is actually in this system, counted twice.

⛔ THE FAILURE THIS STAGE EXISTS FOR: a scan that examined a fraction of its subject produces the
same SHAPE of answer as one that examined all of it. Nothing in the output says "I barely looked".
So the verdict is not "0 findings" -- it is "0 findings across N files, where an independent count
of the same population says N too", and when those two numbers disagree, **the disagreement is the
finding** and the scan reports UNKNOWN rather than clean.

No dependencies, no network, no configuration. It reads; it never writes to the target.
"""
from __future__ import annotations

import os
import sys

__all__ = ["scan", "KINDS", "Result"]

# What a file IS, decided by extension. Deliberately coarse: this stage answers "what is here",
# and a finer classification that guesses wrong is worse than a coarse one that does not.
KINDS = {
    "code": (".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".go", ".rs", ".rb", ".java",
             ".c", ".h", ".cpp", ".cs", ".php", ".swift", ".kt", ".sh", ".bash"),
    "config": (".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env", ".properties"),
    "docs": (".md", ".rst", ".txt", ".adoc"),
    "data": (".csv", ".tsv", ".sql", ".parquet", ".xml", ".ndjson", ".jsonl"),
    "web": (".html", ".css", ".scss", ".sass", ".less", ".svg"),
    "media": (".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov", ".mp3", ".wav", ".pdf"),
}

# Directories that are somebody else's code or a build artefact. Excluded ON PURPOSE and the
# exclusion is REPORTED, because a silent exclusion is how a denominator shrinks unnoticed.
VENDORED = ("node_modules", ".git", ".venv", "venv", "site-packages", "__pycache__",
            ".next", "dist", "build", ".cache", "target", "vendor", ".tox", ".mypy_cache",
            ".pytest_cache", ".gradle", "Pods", ".terraform")


class Result:
    """What the scan found, and -- just as importantly -- what it could not reach."""

    def __init__(self):
        self.by_kind = {}
        self.by_dir = {}
        self.files = 0
        self.bytes = 0
        self.skipped_dirs = {}
        self.unreadable = []
        self.deepest = 0
        self.independent = None      # the second count, from a different method
        self.root = ""

    @property
    def agrees(self):
        """Do the two independent counts agree? None = the second count could not be taken."""
        if self.independent is None:
            return None
        return self.independent == self.files

    def exit_code(self):
        """Three outcomes. A scan that cannot confirm its own population is UNKNOWN, never clean."""
        if not self.files:
            return 2                                  # an empty result is not a finding
        if self.agrees is not True:
            return 2                                  # the counts disagree, or could not be taken
        return 0

    def report(self, out=sys.stdout):
        w = out.write
        w("SCAN  %s\n" % self.root)
        w("=" * 70 + "\n")
        if not self.files:
            w("  NOTHING FOUND. That is UNKNOWN, not clean -- an empty result is no\n"
              "  measurement. Check the path exists and is readable.\n")
            return
        w("  %d file(s), %.1f MB, deepest nesting %d\n"
          % (self.files, self.bytes / 1e6, self.deepest))
        w("\n  WHAT IS HERE\n")
        for kind in list(KINDS) + ["other"]:
            n = self.by_kind.get(kind, 0)
            if n:
                w("    %-8s %6d  %5.1f%%\n" % (kind, n, 100.0 * n / self.files))
        w("\n  WHERE IT IS -- the ten biggest directories\n")
        for d, n in sorted(self.by_dir.items(), key=lambda kv: -kv[1])[:10]:
            w("    %-52s %5d\n" % (d[:52], n))
        if self.skipped_dirs:
            w("\n  DELIBERATELY NOT COUNTED (somebody else's code, or a build artefact)\n")
            for d, n in sorted(self.skipped_dirs.items(), key=lambda kv: -kv[1])[:8]:
                w("    %-20s %d location(s)\n" % (d, n))
        if self.unreadable:
            w("\n  COULD NOT READ %d path(s) -- these are NOT counted as absent\n"
              % len(self.unreadable))
            for p in self.unreadable[:5]:
                w("    %s\n" % p)
        w("\n  THE DENOMINATOR, COUNTED A SECOND WAY\n")
        if self.independent is None:
            w("    UNKNOWN -- the independent count could not be taken, so this scan cannot\n"
              "    confirm it saw everything. Reporting clean here would be a guess.\n")
        elif self.agrees:
            w("    %d, and the walk found %d. They agree.\n" % (self.independent, self.files))
        else:
            w("    ⛔ %d, but the walk found %d -- a difference of %d.\n"
              % (self.independent, self.files, abs(self.independent - self.files)))
            w("    THE DISAGREEMENT IS THE FINDING. One of the two methods is blind, and\n"
              "    until that is explained no verdict from this scan means anything.\n")


def _kind(name):
    ext = os.path.splitext(name)[1].lower()
    for kind, exts in KINDS.items():
        if ext in exts:
            return kind
    return "other"


def _independent_count(root, skip):
    """Count the same population a DIFFERENT way, so the first count can be checked.

    The walk above descends directories. This one asks the operating system to list each
    directory's entries and counts the non-directories. The two agree when both are correct and
    diverge when either has a blind spot -- which is the cheapest completeness proof there is,
    and it needs no knowledge of what SHOULD be there.
    """
    total = 0
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            entries = list(os.scandir(d))
        except OSError:
            return None                 # cannot complete -> no second count, never a guess
        for e in entries:
            try:
                if e.is_dir(follow_symlinks=False):
                    if e.name not in skip:
                        stack.append(e.path)
                elif e.is_file(follow_symlinks=False):
                    total += 1
            except OSError:
                return None
    return total


def scan(root, skip=VENDORED):
    """Discover everything under `root`. Returns a Result. Never writes to `root`."""
    r = Result()
    r.root = os.path.abspath(root)
    if not os.path.isdir(r.root):
        r.unreadable.append("%s is not a directory" % r.root)
        return r
    skip = set(skip)
    base_depth = r.root.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(r.root):
        pruned = [d for d in dirnames if d in skip]
        for d in pruned:
            r.skipped_dirs[d] = r.skipped_dirs.get(d, 0) + 1
        dirnames[:] = [d for d in dirnames if d not in skip]
        depth = dirpath.rstrip(os.sep).count(os.sep) - base_depth
        r.deepest = max(r.deepest, depth)
        # ⛔ NORMALISED ON PURPOSE -- a real Windows-only defect, fixed 2026-09-27. `rel` is a KEY
        # in `by_dir` and is printed in the report, so it is an IDENTIFIER, never a filename to
        # open -- and `os.path.relpath` hands back the PLATFORM's separator. Left alone, this stage
        # reported `ragghost\tests` on Windows and `ragghost/tests` here, while stages 2 and 4 both
        # already normalise and reported the forward-slashed form on both. One tool, two spellings
        # for one directory, and every test passes on each platform separately because nothing ever
        # compares the two. That is the whole shape of a portability bug that CI cannot see.
        rel = os.path.relpath(dirpath, r.root).replace(os.sep, "/")
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            try:
                r.bytes += os.path.getsize(p)
            except OSError:
                r.unreadable.append(p)
                continue
            r.files += 1
            k = _kind(fn)
            r.by_kind[k] = r.by_kind.get(k, 0) + 1
            r.by_dir[rel] = r.by_dir.get(rel, 0) + 1
    r.independent = _independent_count(r.root, skip)
    return r
