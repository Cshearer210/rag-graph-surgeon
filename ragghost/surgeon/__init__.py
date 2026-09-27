"""ragghost.surgeon -- point it at a broken self-built system, and it gets outputs flowing again.

THE SELLING POINT: take a broken system and automatically fix it, then ship the output the owner
actually wanted. The repair is not the product; the WORKING OUTPUT is.

THE ROAD (the pipeline, run by `road.run`):

    1. INTERVIEW  ask the owner: goals, scope, which output to ship. (scope.json for non-interactive)
    2. INGEST     index every file (deterministic, exact) and build a dependency GRAPH of what
                  calls / imports / schedules / enforces what -- population DISCOVERED, never typed.
    3. DIAGNOSE   run the scanners (gates) that find what is broken: broken imports, unwired work,
                  duplicate definitions, missing deps, a generator whose output drifted from source.
    4. WORKSPACE  build an ISOLATED workspace, copy only the files the scope needs, and triage rules:
                  KEEP the ones that help, FLAG the ones that hurt (owner approves), ADD the missing.
    5. FIX        apply the root-cause fix for each diagnosis. Deletion / anything a stranger sees /
                  spending money is REFUSED and surfaced -- the tool proposes, the owner disposes.
    6. BUILD      build the requested OUTPUT along its road (e-commerce store, API, dashboard, ...).
    7. GRADE      grade the output against a rubric; on a fail, RE-RUN the failing step with the
                  specific fix appended (self-improvement), then surface if it still fails.
    8. SHIP       emit the output with PROOF: what changed, what shipped, what the owner must decide.

DESIGN, from FABLE-REPO-PLAN.md:
  - Every FAILURE is a step that depended on someone REMEMBERING; every WORKING part runs whether
    or not anyone remembers. The tool moves maintenance from memory to mechanism.
  - MECHANICAL FIRST. Every stage here runs with no model call, so the demo is $0 and deterministic
    and a stranger can reproduce it. The judgment layers (an ARBITER agent, semantic RAG retrieval,
    a fan-out fleet) are PLUGGABLE via clear interfaces -- see `agents.py` -- and are used only for
    the 5% a single mechanical pass cannot finish. A guessed edge is marked as guessed (graph law 4).
  - THREE OUTCOMES everywhere: PASS / FAIL / UNKNOWN. A check that could not look never reports clean.

⭐ WHY THIS IS `surgeon` AND NOT `doctor`, which is what it was called until 2026-09-27: the CLI
already has `ragghost doctor`, and that means what a stranger expects it to mean -- *check whether
THIS INSTALL works*, the `brew doctor` / `flutter doctor` convention. Two meanings of one word in
one command line would make `ragghost doctor ./my-broken-system` silently ignore the path and
self-check instead. The repository is called rag-graph-surgeon and nothing in it had ever explained
that name; the repair-and-ship road is the surgeon. So:

    ragghost doctor             check yourself
    ragghost surgeon <target>   repair that system and ship its output
"""
# ONE definition of the version, in the package root. A subpackage that declares its own drifts
# from it silently, and then two files disagree about what shipped.
from .. import __version__          # noqa: F401

# Submodules are imported by callers directly (from ragghost.surgeon import road, gates, ...).
# NOT eagerly imported here: that would force every module to exist and be import-clean before any
# one could be tested, which is the opposite of building in slices.
__all__ = ["road", "gates", "graph", "index", "interview", "diagnose", "fix", "workspace",
           "grade", "memory", "agents"]
