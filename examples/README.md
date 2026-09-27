# Examples

Every file here runs in about a second, needs **no index, no network and no dependencies**, and
asserts the verdict it expects — so a failure here is a real change in what the tool claims, not a
flaky demo.

```bash
python3 examples/run_all.py      # all of them; CI runs this too
```

They are also the cheapest way to see what the tool actually says without wiring it to anything.

| File | What it fakes | What `ragghost` should say |
|---|---|---|
| `honest_index.py` | real questions score ~0.86, nonsense ~0.17 | **0** — ranks meaning above noise |
| `lying_index.py` | nonsense 0.735, real questions 0.687 | **1** — nonsense outranks meaning |
| `flat_index.py` | everything scores exactly 0.5 | **1** — a tie is not a pass |
| `refusing_index.py` | answers real questions, returns nothing for nonsense | **0** — and it says it REFUSED, not that it scored well |
| `should_i_fan_out.py` | no index at all — the other half of the tool | six real dispatch decisions |
| `before_after_demo.py` | `broken-shop`, a system with nine planted defects | a repaired copy and a shipped storefront |

## The two that are easy to get wrong

**`flat_index.py`** is the one most graders would pass. Every score is identical, so the gap is
exactly `0.0` — and *"not worse than nonsense"* is not the same as *"better than nonsense"*. An index
that cannot separate anything from anything is broken, and a `>=` where a `>` belongs turns that into
a clean bill of health.

**`refusing_index.py`** is the opposite trap and it is the more dangerous one, because it looks like
the best possible result. An index that declines every nonsense probe separates perfectly from noise
— an infinite gap, a flawless score. It is also completely useless if it declines your real questions
too, and **the numbers alone cannot tell those two apart.** So the verdict names the refusal instead
of celebrating the separation, and what it reports is `nonsense_refused: 18 of 18` rather than a gap.
This one was found by pointing the tool at a real 82,000-chunk index, which refused every probe and
was reported as *"cannot tell"* — the same words as a failed measurement.

## `broken-shop`

`broken-shop/` is not an example you run directly; it is the **system the repair road is pointed at**,
with nine defects planted on purpose — unparseable JSON, a missing config field, an import naming a
module that was renamed, a syntax error, dead code nothing calls, and a rule that pins the project to
the wrong goal. `before_after_demo.py` narrates a run against it, and
`tests/test_surgeon_sandbox.py` asserts the whole story: **three defects fixed, six handed back to a
human, a storefront graded 100%, and the originals never modified.**

```bash
ragghost surgeon examples/broken-shop --output landing --name "Aurora Goods" --out ./shipped
```
