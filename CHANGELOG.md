# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **`ragghost surgeon` — the repair half.** The eight stages read a system and report what is wrong;
  this takes the same system, copies it somewhere safe, applies the fixes that are safe to apply
  mechanically, surfaces the ones that need a human, and then **builds and ships the output you
  wanted**. Four output types, all graded against their own rubric: `landing`, `dashboard`, `api`,
  `cli`. Every step is mechanical — no model call, no network, no cost, same answer every time.
  `python3 -m ragghost.surgeon ...` is the same command.
- `examples/broken-shop`, a system with nine planted defects, and `examples/before_after_demo.py`,
  which narrates the whole story from broken to shipped. The end-to-end is a test
  (`tests/test_surgeon_sandbox.py`), so the demo cannot drift from the tool.
- `ragghost.ranks_meaning` — ask any retrieval index whether real questions outrank nonsense, with
  probes generated fresh at runtime so the fixture cannot be poisoned by the document that explains
  it. Three verdicts: `PASS`, `FAIL`, `CANNOT_TELL`.
- `ragghost.fanout` — decide whether a job should be spread across workers at all, refusing to guess
  when the caller has not said whether the items are judged independently.
- Two more `ragghost doctor` checks, both for the repair half: every module the surgeon names is
  importable **from the install**, and the whole repair road runs end to end on a system built for
  the purpose, requiring a graded output and an untouched original. Six checks in total.

### Fixed
- **It crashed on Windows, and had since release.** Every report marks a finding with `⛔` and a
  caveat with `⚠`; a Windows console runs cp1252, which has neither, so writing a report raised
  `UnicodeEncodeError` and the tool printed a traceback instead of its answer. Both command lines now
  call the new `ragghost.console_safe()` before writing anything. **The reason no test caught it is
  the more useful half:** pytest captures output into a buffer with no code page, so running the
  tests removed the condition, and the Windows job stayed green — while the one Windows step that
  wrote to a real console was `continue-on-error`, because `check` legitimately exits 1 when it finds
  something, so a crash and a finding produced the same tick. `tests/test_console_encoding.py` now
  builds a cp1252 stream itself rather than waiting for a platform to supply one, covering every
  stage's report in both directions, and CI prints a real report with its markers to the runner's own
  console on all three operating systems.
- **Stage 2 (GRAPH) was blind to relative imports.** It followed `import x` and `from x import y` but
  dropped `from . import y` entirely, so a package's internal wiring produced no edges at all and the
  only edges it saw were the ones a test happened to make absolutely. This repository looked clean
  for exactly that reason — until a subpackage arrived whose modules the tests reach only through
  their package, at which point stage 2 called four demonstrably wired files orphans. Relative
  imports now resolve against the importing file's own package at every level, with tests in both
  directions, including the guard that a genuinely un-imported module is still reported.
- A comment in `scan.py` named a `cli` module that has never existed in this package. Stage 2 reports
  it as a dangling reference, which it only can once a file of that basename exists elsewhere in the
  tree and the stale reference starts to resemble the move it looks like.
- A duplicate `"landing"` key in the surgeon's `REQUIRED_FIELDS` — the duplicate-definition class this
  project's own README lists as a defect it looks for in other people's code.
- `packages` in `pyproject.toml` now names the subpackages. With an explicit list, a subpackage left
  out is simply absent from the wheel: `pip install` succeeds, `import ragghost` succeeds, and the
  missing half fails only on a stranger's machine. The two new doctor checks are what make that
  omission loud instead of silent.
- The package docstring claimed *"Stage 1 (SCAN) is working. Stages 2-8 are not built yet"*, seven
  stages after that stopped being true, while the README's status table said all eight worked.
- `nonsense()` probes now begin with a letter. An identifier-shaped tokenizer — including the one in
  `retrieve.py`, its first in-package caller — matches `[A-Za-z_][A-Za-z0-9_]+` and would silently
  drop the first character of a uuid4 hex that starts with a digit, leaving the audit measuring a
  string the caller never constructed.

### Changed
- `retrieve.py`'s noise probe now calls `ranks_meaning.nonsense()` instead of carrying a hardcoded
  literal. The old token appeared in `retrieve.py` itself, and `retrieve.py` is in the corpus whenever
  the tool is pointed at its own repository — so the probe was in the index it was meant to be absent
  from, and a loop quietly mutated it until it was not. One definition, one reader.
- Expanded the test suite to 292 tests covering every module and public function — happy paths,
  boundary values, and error/exception branches — reaching 98% line coverage.
- Property-based tests (`hypothesis`, a dev-only extra) for the fan-out decision and the scanner's
  two-count agreement.
- Shared `tree(...)` pytest fixture in `tests/conftest.py`.
- Project maintenance files: `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `CHANGELOG.md`, issue and pull-request templates, and a Dependabot config.
- `test` optional-dependency group (`pytest`, `hypothesis`, `coverage`) and coverage/ruff
  configuration in `pyproject.toml`.

### Changed
- CI now installs the `test` extras, runs the suite under coverage, and lints with ruff, on
  Python 3.11 and 3.12.

## [0.1.0] - 2026-09-24

### Added
- Initial public release.
- Eight stages, runnable individually or together via `python3 -m ragghost <stage> <path>`:
  1. **SCAN** — discover every file and count the population a second, independent way.
  2. **GRAPH** — a two-way dependency graph; orphans and dangling/moved references.
  3. **ORGANIZE** — a tiered in-place index; load-bearing vs movable files; misfiled files.
  4. **RETRIEVE** — an offline tf-idf retrieval layer that audits itself with a present probe and
     a noise probe.
  5. **HARNESS** — split into subsystems and flag any with no gate.
  6. **PLAN** — a harm-ranked plan built from the real findings of stages 1–5.
  7. **ANALYSE** — decide whether work divides into independent units, and refuse a pointless
     fan-out.
  8. **FIX** — apply only the mechanical, reversible class of fixes and prove each by re-measuring.
- `check` command with `text`, `json`, and `sarif` output for CI.
- Configuration via `.ragghost.json` (`select` / `ignore`) and inline `# ragghost: allow <CODE>`
  suppression.
- Plugin extension point (`ragghost.checks` entry point, or a `ragghost_plugin_*` module).
- Three-outcome exit-code contract: `0` clean · `1` found something · `2` could-not-tell.
- Zero runtime dependencies; MIT licensed.

[Unreleased]: https://github.com/Cshearer210/rag-graph-surgeon/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Cshearer210/rag-graph-surgeon/releases/tag/v0.1.0
