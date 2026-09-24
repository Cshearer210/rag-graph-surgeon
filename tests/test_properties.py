# CALLED BY: pytest -- property-based tests (hypothesis, dev-only).
# FIRES WHEN: asked. Skipped cleanly if hypothesis is not installed.
"""Properties that must hold for ALL inputs, not just the examples a unit test happens to pick.

These target the two pieces of pure logic where an off-by-one or a sign error would slip past
example tests: the fan-out decision, and the scanner's file count vs its independent recount.
"""
import os

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, settings, strategies as st   # noqa: E402

from ragghost.analyse import should_fan_out, MIN_UNITS       # noqa: E402
import importlib
scan = importlib.import_module("ragghost.scan")
from ragghost.scan import _independent_count, VENDORED       # noqa: E402


# ── should_fan_out is a total function with a clear contract ─────────────────
@given(n_units=st.integers(min_value=-50, max_value=200),
       n_cross=st.integers(min_value=0, max_value=200))
def test_fan_out_returns_bool_and_reason(n_units, n_cross):
    fan, reason = should_fan_out(n_units, n_cross)
    assert isinstance(fan, bool)
    assert isinstance(reason, str) and reason


@given(n_units=st.integers(min_value=-50, max_value=200),
       n_cross=st.integers(min_value=1, max_value=200))
def test_any_cross_edge_never_fans_out(n_units, n_cross):
    # a single cross-dependency is enough to force one pass, whatever the unit count
    fan, _ = should_fan_out(n_units, n_cross)
    assert fan is False


@given(n_units=st.integers(max_value=MIN_UNITS - 1))
def test_below_threshold_never_fans_out(n_units):
    fan, _ = should_fan_out(n_units, 0)
    assert fan is False


@given(n_units=st.integers(min_value=MIN_UNITS, max_value=500))
def test_enough_independent_units_always_fan_out(n_units):
    fan, _ = should_fan_out(n_units, 0)
    assert fan is True


# ── the scanner's two counts agree on any tree it can fully read ─────────────
_name = st.text(alphabet="abcdefghij", min_size=1, max_size=6)


@settings(max_examples=40, deadline=None)
@given(files=st.lists(st.tuples(_name, _name), min_size=1, max_size=12, unique=True))
def test_walk_and_independent_count_agree(tmp_path_factory, files):
    root = tmp_path_factory.mktemp("scan_prop")
    for i, (a, b) in enumerate(files):
        rel = os.path.join(str(a), "%s_%d.py" % (b, i))
        p = os.path.join(str(root), rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write("x = 1\n")
    r = scan.scan(str(root))
    assert r.files == len(files)
    assert _independent_count(str(root), set(VENDORED)) == r.files
    assert r.agrees is True
