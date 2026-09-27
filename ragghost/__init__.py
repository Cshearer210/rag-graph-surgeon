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

from .scan import KINDS, Result, scan
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

__all__ = ["scan", "Result", "KINDS", "build_graph", "Graph", "organize", "Index", "build_index", "Retriever", "harnesses", "Harnesses", "plan", "Plan", "analyse", "Analysis", "should_fan_out", "fix", "Fixes", "Fix", "demo", "check", "collect", "Finding", "plugins", "ranks_meaning", "fanout", "surgeon", "__version__"]
