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

__all__ = ["scan", "Result", "KINDS", "build_graph", "Graph", "organize", "Index", "build_index", "Retriever", "__version__"]
__version__ = "0.1.0"
