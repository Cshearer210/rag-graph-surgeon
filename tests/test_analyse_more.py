# CALLED BY: pytest -- extra coverage for stage 7 (ANALYSE).
# FIRES WHEN: asked.
"""Boundary values of the fan-out decision, and the report/exit-code branches of analyse.py."""
import io


from ragghost.analyse import should_fan_out, analyse, Analysis, MIN_UNITS


# ── should_fan_out: the pure decision, at and around its boundaries ─────────
def test_exactly_min_units_and_independent_fans_out():
    fan, reason = should_fan_out(MIN_UNITS, 0)
    assert fan is True
    assert "independent" in reason


def test_one_below_min_units_is_one_pass():
    fan, reason = should_fan_out(MIN_UNITS - 1, 0)
    assert fan is False
    assert "overhead" in reason


def test_any_cross_edge_forces_one_pass():
    fan, reason = should_fan_out(MIN_UNITS + 5, 1)
    assert fan is False
    assert "cross-dependency" in reason


def test_zero_units_is_not_a_fan_out():
    fan, reason = should_fan_out(0, 0)
    assert fan is False
    assert reason == "no units to analyse"


def test_negative_units_is_not_a_fan_out():
    fan, _ = should_fan_out(-3, 0)
    assert fan is False


def test_custom_min_units_lowers_the_bar():
    fan, _ = should_fan_out(3, 0, min_units=2)
    assert fan is True


def test_custom_min_units_raises_the_bar():
    fan, _ = should_fan_out(9, 0, min_units=20)
    assert fan is False


# ── analyse() over a real tree ──────────────────────────────────────────────
def test_interdependent_subsystems_do_not_fan_out(tree):
    # two harnesses, but one imports the other -> a cross edge -> one pass
    d = tree({
        "a/__init__.py": "", "a/m.py": "from b import n\n",
        "b/__init__.py": "", "b/n.py": "def n(): return 1\n",
    })
    a = analyse(d)
    assert a.fan_out is False
    assert a.n_cross_edges >= 1


def test_empty_tree_is_unassessed(tree, tmp_path):
    a = analyse(str(tmp_path))
    assert a.assessed is False
    assert a.exit_code() == 2


# ── exit codes ──────────────────────────────────────────────────────────────
def test_exit_code_one_when_fan_out():
    a = Analysis()
    a.assessed = True
    a.fan_out = True
    assert a.exit_code() == 1


def test_exit_code_zero_when_one_pass():
    a = Analysis()
    a.assessed = True
    a.fan_out = False
    assert a.exit_code() == 0


# ── report() branches ───────────────────────────────────────────────────────
def test_report_one_pass_explains_the_saving(tree):
    d = tree({
        "a/__init__.py": "", "a/m.py": "from b import n\n",
        "b/__init__.py": "", "b/n.py": "def n(): return 1\n",
    })
    buf = io.StringIO()
    analyse(d).report(buf)
    text = buf.getvalue()
    assert "ONE PASS" in text
    assert "save its entire cost" in text


def test_report_unassessed_is_unknown():
    a = Analysis()
    a.root = "/x"
    buf = io.StringIO()
    a.report(buf)
    assert "NOTHING TO ANALYSE" in buf.getvalue()


def test_report_fan_out_verdict():
    a = Analysis()
    a.root = "/x"
    a.assessed = True
    a.n_units = 10
    a.fan_out = True
    a.reason = "10 independent unit(s)"
    buf = io.StringIO()
    a.report(buf)
    assert "FAN OUT" in buf.getvalue()
