# RAG-Ghost

**Point it at a broken system. It tells you what is actually there, what is wired to what, what
is lying to you, and then fixes what it can.**

Most tools that audit a codebase answer *"is this file OK?"*. RAG-Ghost asks the opposite
question — *"does everything this system promises, points at, or schedules actually exist and
fire?"* — because that is where the failures that survive for months live.

---

## Why it exists

A system does not usually break loudly. It breaks like this:

- a check that has run green every night for five weeks **and has never once looked at anything**
- a scheduled job whose file was renamed, so the scheduler runs nothing and reports success
- a tool that was built, is correct, passes its own tests, and **nothing calls it**
- a document that says a thing is fixed, written before the thing broke again
- a count that shrank because the scan got narrower, not because the problem got smaller

Every one of those is invisible from the inside. A clean report and an unasked question look
identical. **RAG-Ghost is built to tell them apart.**

---

## The eight stages

| # | stage | what it does |
|---|---|---|
| 1 | **SCAN** | discover every file and every population, with a denominator that comes from a second, independent count |
| 2 | **GRAPH** | a dependency graph both ways — what breaks if this changes, and what breaks if this moves |
| 3 | **ORGANIZE** | sort files into a tiered structure; index what must not move rather than moving it |
| 4 | **RETRIEVE** | build the retrieval layer so the system can answer questions about itself — and audit that layer, because a retriever that returns nothing looks like a system with nothing in it |
| 5 | **HARNESS** | separate the system into harnesses with gates, checks and doors |
| 6 | **PLAN** | generate a ranked plan of what should be done, from the real state |
| 7 | **ANALYSE** | fan out parallel workers to judge what does not fit in one pass — and refuse the fan-out where the work does not actually divide |
| 8 | **FIX** | apply what can be applied mechanically, and prove each fix with a check that fires on its own |

**All eight stages work today.** This README will never claim otherwise — see *Status*, below.

---

## Three rules it holds itself to

**1. Three outcomes, three exit codes.** `0` clean · `1` found something · `2` could not tell.
A check that cannot look must never report clean. Most tools have two outcomes, which is why
"nothing found" and "nothing worked" are so often the same output.

**2. Every number carries its denominator, and the denominator comes from somewhere else.**
`0 findings` is unfalsifiable. `0 findings across 1,412 files, where the disk holds 1,412` is
checkable by anyone in two seconds — and when the two counts disagree, **the disagreement is the
finding.**

**3. A population is discovered, never typed.** A hand-written list of things to check is a list
of what somebody remembered, and the thing nobody remembered is where the bug is.

---

## See it in 15 seconds

![rag-ghost demo — a tiny system with four planted problems, examined live](assets/demo.svg)

```
$ python3 -m ragghost demo
GRAPH  -> orphans: ['exporter.py', 'labels.py', 'sync.py']
          dangling: ['inventory/sync.py -> inventory.warehouse']
ORGANIZE -> misfiled: ['test_sync.py']
HARNESS  -> ungated subsystems: ['reports', 'shipping']
PLAN     -> 7 action(s), worst first:
             [moved-ref] a named path resolves to nothing -- update the reference or restore the file
             [no-gate ] a code subsystem no test guards -- add a gate before trusting it
             [orphan  ] nothing depends on this file -- wire it in, or delete it if it is dead
ANALYSE  -> ONE PASS: only 4 units; the per-worker overhead would exceed the work
FIX (dry run) -> 1 mechanical fix it can apply and PROVE, 6 that need a human
```

`python3 -m ragghost demo` builds a tiny broken system in a temp dir and runs every stage against
it, live — so the demo can never drift from the tool.

## Install and run

No dependencies. No account. No API key. No network.

```bash
git clone <this repo> && cd rag-ghost
python3 -m ragghost demo                          # the 15-second tour
python3 -m ragghost scan /path/to/any/system      # then point it at a real system
```

It will not write to the system it is pointed at. The one exception is stage 8 (`fix`), which is a
dry run by default and writes only the mechanical, reversible fixes when you add `--apply` — and
re-measures the world after each edit, rolling it back if the defect is not actually gone.

---

## Drops into CI

```bash
python3 -m ragghost check .                 # every finding, ranked, human-readable
python3 -m ragghost check . --format json   # for a script
python3 -m ragghost check . --format sarif  # for GitHub code scanning / a dashboard
```

Exit `0` clean · `1` found something · `2` could-not-tell (never treat as clean).

- **Choose which checks run** — a `.ragghost.json` in the target root:
  `{"select": ["GRAPH-DANGLING"], "ignore": ["ORG-MISFILED"]}` (by code, or by family like `GRAPH`).
- **Silence one on a single file** — a line in that file: `# ragghost: allow GRAPH-ORPHAN`
  (or `# ragghost: allow ALL`). Explicit, local, and visible in review.
- **Add your own check** — register a callable under the `ragghost.checks` entry point, or ship a
  `ragghost_plugin_*` module exposing `CHECKS = [fn]`. A plugin that raises is reported and skipped,
  never silently dropping the run to a clean result.

Codes: `SCAN-DRIFT` · `GRAPH-ORPHAN` · `GRAPH-DANGLING` · `ORG-MISFILED` · `HARNESS-NOGATE` · `RETR-BLIND`.

## Status, honestly

| stage | state |
|---|---|
| 1 SCAN | **working** — discovers files, classifies them, counts two independent ways, reports drift |
| 2 GRAPH | **working** — dependency graph both directions; dangling refs and orphans |
| 3 ORGANIZE | **working** — tiered index; what is load-bearing vs movable; misfiled files |
| 4 RETRIEVE | **working** — offline tf-idf index; audits itself with a present probe and a noise probe |
| 5 HARNESS | **working** — splits into subsystems; flags any with no gate |
| 6 PLAN | **working** — a harm-ranked plan built from the real findings of stages 1–5 |
| 7 ANALYSE | **working** — decides if the work divides; refuses a fan-out that would not pay off |
| 8 FIX | **working** — dry-run by default; applies only the mechanical class and proves each edit |

This table is the only place status is claimed, and it is updated in the same commit as the work.
A README that describes a version that was never shipped is the first defect this tool looks for
in somebody else's repo, so it would be a poor place to start.

## Known limits — what it does NOT catch yet

Measured by pointing it at a test bed with one planted example of every issue type (see
`carrot-sandbox`). The wiring layer is covered; these are the next things to build, named honestly
rather than left to look covered:

- **symbol-level dead code** — a function exported but never *called* (file-level orphans are caught; symbol-level are not yet).
- **duplicate definitions** — the same symbol defined in two files, where fixing one leaves the other stale.
- **test-shape rot** — a test that asserts nothing, swallows its own exception, or is permanently skipped.
- **config rot** — a config key nothing reads, or an env var referenced but set nowhere.
- **a doc that names a script/path that does not exist** (a ghost pointer).

None of these are silently mishandled — they are simply out of scope today, and each is a planned
stage. Mutation-based checks (a test that passes because the code cannot make it fail) are
[`deadcanary`](https://github.com/Cshearer210/claimproof/tree/main/packages/deadcanary)'s job.
