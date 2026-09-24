# CALLED BY: pytest -- shared fixtures for the ragghost test suite.
# FIRES WHEN: pytest collects the tests/ directory.
"""Shared helpers so every test file builds a fixture tree the same way.

`build(root, files)` writes a mapping of repo-relative path -> file body into a real directory,
creating parents as needed. `tree` is a pytest fixture that hands back a callable bound to a fresh
tmp_path, so a test can write `tree({...})` and get the directory path back.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def build(root, files):
    """Write {relative_path: body} under root. Returns root for convenience."""
    for rel, body in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p) or root, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)
    return root


@pytest.fixture
def tree(tmp_path):
    """Return a callable that materialises a fixture tree under a fresh temp dir and returns it."""
    def _make(files):
        return build(str(tmp_path), files)
    return _make
