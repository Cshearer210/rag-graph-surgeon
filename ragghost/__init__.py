# CALLED BY: ragghost/__main__.py (the `ragghost` console script), ragghost/surgeon/*, tests/*.
# FIRES WHEN: asked -- the package entry point of a standalone tool run by whoever downloads it.
"""RAG-Ghost: point it at a broken system, find out what is actually there, then get it working.

TWO HALVES, and they stay separate on purpose:

  the EIGHT STAGES (`scan` .. `fix`)   READ a system and report what is wrong. Stages 1-7 never
                                      write anything; stage 8 writes only with `--apply`.
  `ragghost.surgeon`                   REPAIRS an isolated COPY and SHIPS the output the owner
                                      asked for. The repair is not the product; the output is.

⛔ THE DOCSTRING THAT WAS HERE CLAIMED "Stage 1 (SCAN) is working. Stages 2-8 are not built yet",
which stopped being true seven stages ago while `README.md`'s status table said all eight were
working. A file that describes a version which was never shipped is the first thing this tool looks
for in somebody else's repo, so it is a poor thing to carry in its own entry point. Corrected
2026-09-27. Per-stage status is claimed in ONE place, `README.md`.

⚠ `__version__` IS DEFINED FIRST, ABOVE THE IMPORTS, AND THAT ORDER IS LOAD-BEARING: `surgeon`
reads it from here rather than declaring a second copy, so it must exist before `from . import
surgeon` runs. Two definitions of one version is the defect, and it drifts silently.
"""
__version__ = "0.2.0"

import sys as _sys


def console_safe(*streams):
    """Stop a report crashing on a console that cannot encode the characters in it.

    ⛔ THE DEFECT THIS FIXES WAS SHIPPED AND USER-FACING. Every stage's report marks a finding with
    `⛔` and a caveat with `⚠`, and a Windows console defaults to the cp1252 code page, which has no
    such characters. So `sys.stdout.write` raised `UnicodeEncodeError` and the tool died with a
    traceback instead of printing its answer -- on Windows, for any report that found anything.

    ⚠ AND NOTHING CAUGHT IT FOR THREE DAYS, WHICH IS THE MORE USEFUL HALF. The Windows test job was
    green the whole time, because pytest captures output into a buffer that has no code page at all,
    so the very act of testing removed the condition. The one Windows step that printed to a real
    console was `ragghost check .`, and it was marked `continue-on-error` for a legitimate reason --
    `check` exits 1 when it finds something -- which meant a CRASH and a FINDING produced the same
    green tick. Found 2026-09-27 when a `⚠` added to the help text made `ragghost --help` fail, and
    `--help` is the one step that had no honest reason to tolerate an error.

    It MUTATES the stream rather than replacing it, which matters here: several `report()` functions
    bind `out=sys.stdout` as a default argument at import time, so rebinding `sys.stdout` afterwards
    would not reach them. Reconfiguring the object they already hold does.

    Called by both command lines. It is NOT called on import: a library that quietly reconfigures a
    process's streams because somebody imported it is a worse citizen than one that crashes honestly,
    so an embedder who prints our reports themselves calls this first -- which is why it is public.
    """
    targets = streams or (_sys.stdout, _sys.stderr)
    for s in targets:
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                        # noqa: BLE001
            # Not a reconfigurable text stream (a pipe wrapper, a test double, an old Python).
            # Keeping the console's own encoding and only softening the error is still a fix: the
            # marker degrades to `?` and the report is still readable, which beats a traceback.
            try:
                s.reconfigure(errors="replace")
            except Exception:                                    # noqa: BLE001
                pass
    return targets


from .scan import KINDS, Result, scan   # noqa: E402  -- must follow console_safe, which scan may use
from .graph import Graph, build_graph
from .organize import Index, organize
from .retrieve import Retriever, build_index
from .harness import Harnesses, harnesses
from .plan import Plan, plan
from .analyse import Analysis, analyse, should_fan_out
from .fix import Fix, Fixes, fix
from .demo import main as demo
from .report import check, collect, Finding
from . import plugins
from . import ranks_meaning
from . import fanout
# The subpackage itself is tiny and imports nothing; its 18 modules are NOT pulled in here, so
# `import ragghost` stays cheap. Imported rather than merely named because `ragghost doctor`
# resolves every name in __all__ against the INSTALL, and a name nothing imports would fail there.
from . import surgeon

__all__ = ["scan", "Result", "KINDS", "build_graph", "Graph", "organize", "Index", "build_index", "Retriever", "harnesses", "Harnesses", "plan", "Plan", "analyse", "Analysis", "should_fan_out", "fix", "Fixes", "Fix", "demo", "check", "collect", "Finding", "plugins", "ranks_meaning", "fanout", "surgeon", "console_safe", "__version__"]
