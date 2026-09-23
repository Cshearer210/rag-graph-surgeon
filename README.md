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

**Stages 1 through 6 work today.** The rest are being built in order, and this README will never claim
otherwise — see *Status*, below.

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

## Install and run

No dependencies. No account. No API key. No network.

```bash
git clone <this repo> && cd rag-ghost
python3 -m ragghost scan /path/to/any/system
```

It will not write to the system it is pointed at.

---

## Status, honestly

| stage | state |
|---|---|
| 1 SCAN | **working** — discovers files, classifies them, counts two independent ways, reports drift |
| 2–8 | not built yet |

This table is the only place status is claimed, and it is updated in the same commit as the work.
A README that describes a version that was never shipped is the first defect this tool looks for
in somebody else's repo, so it would be a poor place to start.
