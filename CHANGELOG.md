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
- `ragghost.ranks_meaning` — ask any retrieval index whether real questions outrank nonsense. Probes
  are generated fresh at runtime in **three shapes** (hex, word-shaped, punctuation) so the fixture
  cannot be poisoned by the document that explains it; the comparison is **median to median** with a
  separate verdict for overlapping ranges; a missing score is dropped, never read as zero; hits in
  the asking session's own files are discarded as self-echo; and an index that **refuses** every
  nonsense probe is reported as the strongest possible pass rather than as an unmeasurable one.
  `Verdict.code` is `0` clean / `1` problem / `2` cannot tell — the same three outcomes as every
  stage.
- `ragghost.fanout` — decide whether a job should be spread across workers at all. **Nine named
  shapes**, four of which divide; an unrecognised shape is `cannot tell` and never a yes, because the
  permissive answer here spends real money. It refuses a cap of zero (a fan-out that dispatches
  nothing is not a fan-out) and names how many items a cap would silently drop.
- `examples/` — five runnable examples with no index required: an honest index, one that **lies
  exactly the way a real one did**, a flat index every naive grader passes, a refusal that looks like
  a perfect score, and the fan-out decision over six real dispatch calls. `examples/run_all.py` runs
  all of them plus the repair-road demo, and **CI runs it** — an example that has quietly stopped
  working is worse than no example, because it is the first thing a stranger tries.
- `tools/run_against_real_index.py` — point the retrieval audit at your own live index. This is the
  step that makes the tool honest: a test suite proves internal consistency and says nothing about
  whether a verdict is TRUE of a real system.
- `tests/test_hostile.py` — 23 cases of broken, empty, hostile and huge input across both library
  judgements. The bar is not "it does not crash": given input that cannot support a verdict the answer
  must be `cannot tell` or an honest `found`, and **never** a confident clean.
- Two more `ragghost doctor` checks, both for the repair half: every module the surgeon names is
  importable **from the install**, and the whole repair road runs end to end on a system built for
  the purpose, requiring a graded output and an untouched original. Six checks in total.

### Fixed
- **Stage 4's noise probe is now verified ABSENT before it is used, so `check` is deterministic.**
  Found by running `ragghost check .` ten times on an unchanged tree: one run in ten reported
  `RETR-BLIND, noise scored 0.175`. The probe had been changed from a hardcoded literal — which
  carried a `while noise in self.index` loop guaranteeing absence — to a random `wordlike` draw, and
  a short syllable like `wose` or `tico` can genuinely be a token in a real corpus. The probe was
  *usually* absent and not *reliably* absent. **A check that gives two answers about one unchanged
  tree is worse than a wrong one: nobody can tell which run to believe, and it teaches a reader to
  re-run a real finding away.** It now redraws until every token is absent, and says **UNKNOWN** if
  no absent probe can be built at all, rather than inventing either a pass or a finding.
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
- Nonsense probes for an in-package caller now come from the `wordlike` shape, which always begins
  with a letter. An identifier-shaped tokenizer — including the one in `retrieve.py`, the first
  in-package caller — matches `[A-Za-z_][A-Za-z0-9_]+`, so a `hex` probe beginning with a digit loses
  its first character and a `punct` probe is discarded entirely. The probe would still be absent from
  the corpus, so the audit would still pass, while measuring a string the caller never constructed.
- **A `query_fn` that raises is now named as such**, instead of being reported as too small a sample.
  Both produced the words *"not enough probes to tell"* — two different problems with one message,
  and the one that needs fixing is not the one the message describes. It happened here: an example
  lost its `import random` in a rewrite, every call raised `NameError`, and the verdict blamed the
  sample size.
- **Both `ranks_meaning` and `fanout` were replaced by more mature versions of themselves**, which is
  a merge rather than a rewrite. Two versions of each existed in unpublished work and the weaker one
  shipped first, because whoever published it did not know the other was there. The survivors bring
  three shapes of nonsense instead of one, median-based comparison, the minimum-probe floor,
  self-echo filtering, named fan-out shapes instead of a row of booleans, and a `code` that is already
  this tool's `0/1/2`. What the losers contributed and kept their place for: the return-shape adapter
  (so you can point the audit at an index you already have without writing a wrapper first) and the
  measured cost of a barrier — two stopped fleets lost 2.26M tokens for zero results that way.

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
