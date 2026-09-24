# Contributing to rag-graph-surgeon

Thanks for considering a contribution. This is a small, deliberately zero-dependency tool, and the
bar for a change is that it makes the tool *more honest* — better at telling "clean" apart from
"could not look" — without adding runtime dependencies.

## Ground rules

- **The runtime stays dependency-free.** The tool must import only the Python standard library.
  Test-only and lint-only tooling is fine (see the `test` extra in `pyproject.toml`).
- **Every check earns its keep in both directions.** A detector must be shown to *fire* on a real
  planted defect *and* stay *quiet* on a clean look-alike. A test that can only ever pass is the
  blind spot this project exists to remove.
- **Three outcomes, three exit codes:** `0` clean · `1` found something · `2` could-not-tell. A
  check that cannot look must never return `0`.
- **Status is claimed in exactly one place** (the *Status* table in the README) and updated in the
  same commit as the work.

## Setup

Requires Python 3.11 or newer.

```bash
git clone https://github.com/Cshearer210/rag-graph-surgeon
cd rag-graph-surgeon
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -e ".[test]"     # pytest + hypothesis + coverage; none needed to RUN the tool
```

## Run the tests

```bash
python3 -m pytest -q tests
```

With coverage:

```bash
python3 -m coverage run -m pytest -q tests
python3 -m coverage report          # show line coverage per module
```

Lint (matches CI):

```bash
python3 -m pip install ruff
ruff check ragghost tests
```

The tool also holds itself to its own standard — this must exit `0`:

```bash
python3 -m ragghost check .
```

## Writing tests

- Put new tests under `tests/`. The shared `tree(...)` fixture (in `tests/conftest.py`) builds a
  fixture directory from a `{relative_path: body}` mapping.
- Assert **real behaviour on a known input**. No vacuous tests: never `assert True`, never a test
  with no assertion, never a test that only imports.
- For a new detector, add a must-fire case and a must-stay-quiet look-alike.
- Property-based tests belong in `tests/test_properties.py` and use `hypothesis` (dev-only). They
  are skipped cleanly if `hypothesis` is not installed.

## Pull request flow

1. Fork and create a branch off `main` (e.g. `fix/dangling-symlink`).
2. Make the change. Add or update tests in the same PR.
3. Ensure `ruff check`, `python3 -m pytest -q tests`, and `python3 -m ragghost check .` all pass.
4. Update `CHANGELOG.md` under the `[Unreleased]` heading.
5. Open the PR using the template. Describe what was broken, the fix, and how a reviewer can verify
   it. Link any related issue.

CI runs the suite and ruff on Python 3.11 and 3.12; both must be green before review.

By contributing, you agree that your contributions are licensed under the project's
[MIT License](LICENSE).
