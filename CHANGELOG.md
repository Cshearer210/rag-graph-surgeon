# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
