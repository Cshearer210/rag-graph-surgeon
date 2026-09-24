# CALLED BY: pytest -- coverage for the plugin extension point.
# FIRES WHEN: asked.
"""register / registered / discover / run_plugins, including the contract that a raising plugin is
logged and skipped rather than taking the whole run down."""
import pytest

from ragghost import plugins
from ragghost.report import Finding


@pytest.fixture(autouse=True)
def clean_registry():
    """Every test starts and ends with an empty in-process registry and error log."""
    saved_reg = list(plugins._REGISTRY)
    saved_err = list(plugins.load_errors)
    plugins._REGISTRY.clear()
    plugins.load_errors.clear()
    yield
    plugins._REGISTRY[:] = saved_reg
    plugins.load_errors[:] = saved_err


def test_register_adds_to_registry_and_returns_the_function():
    def my_check(root):
        return []
    returned = plugins.register(my_check)
    assert returned is my_check
    assert my_check in plugins.registered()


def test_register_is_idempotent():
    def my_check(root):
        return []
    plugins.register(my_check)
    plugins.register(my_check)
    assert plugins.registered().count(my_check) == 1


def test_registered_returns_a_copy():
    def my_check(root):
        return []
    plugins.register(my_check)
    snapshot = plugins.registered()
    snapshot.append("intruder")
    assert "intruder" not in plugins._REGISTRY


def test_discover_deduplicates():
    @plugins.register
    def dup(root):
        return []
    found = plugins.discover()
    keys = [getattr(fn, "__qualname__", repr(fn)) for fn in found]
    assert keys.count("test_discover_deduplicates.<locals>.dup") == 1


def test_run_plugins_collects_findings():
    @plugins.register
    def good(root):
        return [Finding("PLUGIN-OK", "LOW", "found by a plugin", "detail", "a.py")]
    findings = plugins.run_plugins("/some/root")
    assert any(f.code == "PLUGIN-OK" for f in findings)


def test_run_plugins_tolerates_a_none_return():
    @plugins.register
    def returns_none(root):
        return None
    # must not raise; a None return contributes no findings
    assert plugins.run_plugins("/root") == []


def test_a_raising_plugin_is_logged_and_skipped():
    @plugins.register
    def explodes(root):
        raise RuntimeError("boom")

    @plugins.register
    def steady(root):
        return [Finding("STEADY", "LOW", "m", "d", "a.py")]

    findings = plugins.run_plugins("/root")
    # the good plugin still ran...
    assert any(f.code == "STEADY" for f in findings)
    # ...and the bad one was recorded, not fatal
    assert any("explodes" in name for name, _ in plugins.load_errors)


def test_discover_includes_entry_points_and_local_modules_without_error():
    # these two discovery sources may find nothing in a bare test env, but must not raise
    eps = plugins._from_entry_points()
    locals_ = plugins._from_local_modules()
    assert isinstance(eps, list)
    assert isinstance(locals_, list)
