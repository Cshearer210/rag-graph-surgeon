# CALLED BY: ragghost/cli.py and tests/test_scan.py
# FIRES WHEN: asked -- the package entry point of a standalone tool run by whoever downloads it.
"""RAG-Ghost: point it at a broken system and find out what is actually there.

Stage 1 (SCAN) is working. Stages 2-8 are not built yet, and `README.md` says so in the one
place status is claimed.
"""
from .scan import KINDS, Result, scan
from .graph import Graph, build_graph
from .organize import Index, organize
from .retrieve import Retriever, build_index
from .harness import Harnesses, harnesses
from .plan import Plan, plan
from .analyse import Analysis, analyse, should_fan_out
from .fix import Fix, Fixes, fix
from .demo import main as demo

__all__ = ["scan", "Result", "KINDS", "build_graph", "Graph", "organize", "Index", "build_index", "Retriever", "harnesses", "Harnesses", "plan", "Plan", "analyse", "Analysis", "should_fan_out", "fix", "Fixes", "Fix", "demo", "__version__"]
__version__ = "0.1.0"
