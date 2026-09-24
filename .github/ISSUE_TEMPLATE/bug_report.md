---
name: Bug report
about: Report something that behaves incorrectly
title: "[bug] "
labels: bug
assignees: ''
---

## What happened

A clear description of the bug.

## What you expected

What you expected to happen instead. If a stage reported "clean" (`0`) when it should have found
something (`1`) or could-not-tell (`2`), say which.

## Steps to reproduce

```bash
# the exact command(s) you ran, e.g.
python3 -m ragghost graph /path/to/system
```

If you can, describe (or attach) the smallest directory layout that triggers it. A `python3 -m
ragghost demo`-style minimal tree is ideal.

## Actual output

```
paste the real output here, including the exit code
```

## Environment

- rag-graph-surgeon version or commit:
- Python version (`python3 --version`):
- OS / platform:

## Anything else

Logs, screenshots, or context that might help.
