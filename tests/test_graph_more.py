# CALLED BY: pytest -- extra coverage for stage 2 (GRAPH).
# FIRES WHEN: asked.
"""Transitive dependents, the module map, and every report branch of graph.py."""
import io


from ragghost.graph import (build_graph, Graph, _py_module_map, _imports, _own_package,
                            _from_targets, _defined_names)


# ── relative imports: the blind spot that made four wired files read as orphans ──
#
# Stage 2 used to drop every relative import, so a package's internal wiring was invisible and the
# only edges it saw were the ones a test happened to make absolutely. Both directions below: the
# must-fire half is that the edge now EXISTS and the file is not an orphan; the guard half is that
# a genuinely un-imported module is still reported, so the fix did not simply stop the check firing.

def test_a_dotted_relative_import_creates_an_edge(tree):
    d = tree({
        "pkg/__init__.py": "from . import sub\n",
        "pkg/sub/__init__.py": "from . import worker\n",
        "pkg/sub/worker.py": "def go():\n    return 1\n",
    })
    g = build_graph(d)
    assert "pkg/sub/worker.py" in g.edges["pkg/sub/__init__.py"], \
        "`from . import worker` inside a subpackage must be an edge, not nothing"
    assert "pkg/sub/worker.py" not in g.orphans, \
        "a module its own package imports is wired; calling it an orphan is the false positive"


def test_from_dot_module_import_name_resolves(tree):
    d = tree({
        "pkg/__init__.py": "",
        "pkg/caller.py": "from .helper import go\n\ngo()\n",
        "pkg/helper.py": "def go():\n    return 1\n",
    })
    g = build_graph(d)
    assert "pkg/helper.py" in g.edges["pkg/caller.py"]
    assert "pkg/helper.py" not in g.orphans


def test_a_parent_relative_import_walks_up_the_right_number_of_levels(tree):
    d = tree({
        "pkg/__init__.py": "",
        "pkg/shared.py": "VALUE = 1\n",
        "pkg/deep/__init__.py": "",
        "pkg/deep/user.py": "from ..shared import VALUE\n",
    })
    g = build_graph(d)
    assert "pkg/shared.py" in g.edges["pkg/deep/user.py"], \
        "`..` must resolve to the PARENT package, not to the file's own"


def test_an_unimported_module_is_still_an_orphan(tree):
    """THE GUARD. Resolving relative imports must not make the orphan check unable to fire."""
    d = tree({
        "pkg/__init__.py": "from . import used\n",
        "pkg/used.py": "X = 1\n",
        "pkg/never_imported.py": "Y = 2\n",
    })
    g = build_graph(d)
    assert "pkg/never_imported.py" in g.orphans
    assert "pkg/used.py" not in g.orphans


def test_own_package_distinguishes_an_init_from_a_module():
    """An __init__ IS its package; a module lives IN its parent. One level of error here points
    every relative import in the tree at a module that does not exist."""
    assert _own_package("pkg/sub/__init__.py") == "pkg.sub"
    assert _own_package("pkg/sub/mod.py") == "pkg.sub"
    assert _own_package("top.py") == ""


def test_imports_without_a_rel_skips_relative_rather_than_guessing(tree):
    """Called with no repo-relative path there is nothing to resolve against, so the honest answer
    is to skip -- never to invent a package name."""
    d = tree({"pkg/__init__.py": "", "pkg/m.py": "from . import other\nimport os\n"})
    got = _imports(_abs(d, "pkg/m.py"))          # deliberately no rel=
    assert "os" in got
    assert not any(m.startswith("pkg") for m in got)


def _abs(root, rel):
    import os
    return os.path.join(root, rel)


# ── dependents(): the transitive-closure question the graph exists to answer ─
def test_dependents_are_transitive(tree):
    d = tree({
        "pkg/__init__.py": "",
        "pkg/a.py": "from pkg import b\n",
        "pkg/b.py": "from pkg import c\n",
        "pkg/c.py": "VALUE = 1\n",
    })
    g = build_graph(d)
    deps = g.dependents("pkg/c.py")
    assert "pkg/b.py" in deps
    assert "pkg/a.py" in deps          # transitive through b


def test_dependents_of_a_leaf_is_empty(tree):
    d = tree({"pkg/__init__.py": "", "pkg/a.py": "from pkg import b\n", "pkg/b.py": "X=1\n"})
    g = build_graph(d)
    assert g.dependents("pkg/a.py") == set()


def test_dependents_of_unknown_path_is_empty(tree):
    d = tree({"a.py": "X=1\n"})
    g = build_graph(d)
    assert g.dependents("does/not/exist.py") == set()


# ── the module map that resolves imports to files ───────────────────────────
def test_module_map_handles_package_and_bare_name():
    nodes = {"pkg/__init__.py", "pkg/core.py", "top.py"}
    m = _py_module_map(nodes)
    assert m["pkg"] == "pkg/__init__.py"       # __init__ maps to the package name
    assert m["pkg.core"] == "pkg/core.py"
    assert m["core"] == "pkg/core.py"          # bare-name fallback
    assert m["top"] == "top.py"


def test_module_map_ignores_non_python():
    m = _py_module_map({"a.py", "b.txt", "c.json"})
    assert "a" in m
    assert "b" not in m and "c" not in m


# ── the AST helpers return None (UNKNOWN), never a wrong answer, on bad input ─
def test_imports_returns_none_on_syntax_error(tree):
    d = tree({"broken.py": "def (:\n"})
    assert _imports(_abs(d, "broken.py")) is None


def test_imports_reads_import_and_from(tree):
    d = tree({"m.py": "import os\nfrom collections import OrderedDict\n"})
    mods = _imports(_abs(d, "m.py"))
    assert "os" in mods
    assert "collections" in mods
    assert "collections.OrderedDict" in mods


def test_from_targets_returns_none_on_syntax_error(tree):
    d = tree({"broken.py": "from x import (\n"})
    assert _from_targets(_abs(d, "broken.py")) is None


def test_from_targets_skips_star_imports(tree):
    d = tree({"m.py": "from pkg import *\nfrom pkg import real\n"})
    targets = _from_targets(_abs(d, "m.py"))
    assert ("pkg", "real") in targets
    assert all(name != "*" for _, name in targets)


def test_defined_names_collects_top_level_symbols(tree):
    d = tree({"__init__.py": "import os\nX = 1\ndef fn(): pass\nclass K: pass\n"})
    names = _defined_names(_abs(d, "__init__.py"))
    assert {"os", "X", "fn", "K"} <= names


def test_defined_names_returns_none_on_syntax_error(tree):
    d = tree({"__init__.py": "class (:\n"})
    assert _defined_names(_abs(d, "__init__.py")) is None


# ── build_graph structural facts ────────────────────────────────────────────
def test_non_python_files_are_nodes_but_have_no_edges(tree):
    d = tree({"a.py": "X=1\n", "data.json": "{}", "notes.md": "hi"})
    g = build_graph(d)
    assert "data.json" in g.nodes
    assert g.edges["data.json"] == set()


def test_edges_and_reverse_edges_agree(tree):
    d = tree({"pkg/__init__.py": "", "pkg/a.py": "from pkg import b\n", "pkg/b.py": "X=1\n"})
    g = build_graph(d)
    assert "pkg/b.py" in g.edges["pkg/a.py"]
    assert "pkg/a.py" in g.rev["pkg/b.py"]


def test_third_party_imports_are_not_edges(tree):
    d = tree({"a.py": "import os\nimport json\n"})
    g = build_graph(d)
    assert g.edges["a.py"] == set()      # stdlib is never an internal edge


def test_broken_submodule_ref_skips_external_packages(tree):
    # `from collections import Nonesuch` -- collections is not a package we own, so no dangling
    d = tree({"a.py": "from collections import Nonesuch\n"})
    g = build_graph(d)
    assert g.dangling == []


# ── report() branches ───────────────────────────────────────────────────────
def test_report_lists_most_depended_on(tree):
    d = tree({
        "pkg/__init__.py": "",
        "pkg/core.py": "X=1\n",
        "pkg/a.py": "from pkg import core\n",
        "pkg/b.py": "from pkg import core\n",
    })
    buf = io.StringIO()
    build_graph(d).report(buf)
    assert "MOST DEPENDED ON" in buf.getvalue()


def test_report_flags_orphans_and_dangling(tree):
    d = tree({
        "inventory/__init__.py": "",
        "inventory/sync.py": "from inventory import warehouse\n",
        "reports/__init__.py": "",
        "reports/exporter.py": "def e(): return 1\n",
    })
    buf = io.StringIO()
    build_graph(d).report(buf)
    text = buf.getvalue()
    assert "NOTHING DEPENDS ON" in text
    assert "RESOLVE TO NOTHING" in text


def test_report_clean_wiring_message(tree):
    d = tree({"pkg/__init__.py": "", "pkg/__main__.py": "from pkg import core\n",
              "pkg/core.py": "X=1\n"})
    buf = io.StringIO()
    build_graph(d).report(buf)
    assert "Nothing hidden at the wiring layer." in buf.getvalue()


def test_report_names_unparsed_files(tree):
    d = tree({"pkg/__init__.py": "", "pkg/__main__.py": "from pkg import ok\n",
              "pkg/ok.py": "X=1\n", "pkg/broken.py": "def (:\n"})
    buf = io.StringIO()
    build_graph(d).report(buf)
    assert "COULD NOT PARSE" in buf.getvalue()


def test_report_on_empty_graph_is_unknown():
    g = Graph()
    g.root = "/x"
    buf = io.StringIO()
    g.report(buf)
    assert "UNKNOWN" in buf.getvalue()


def test_empty_graph_exit_code_is_two():
    assert Graph().exit_code() == 2
