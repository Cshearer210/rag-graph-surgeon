## What this changes

A short description of the change and the problem it solves.

Fixes # (issue number, if any)

## Type of change

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New detector / feature (non-breaking change that adds capability)
- [ ] Breaking change (fix or feature that changes existing behaviour)
- [ ] Docs / tests / tooling only

## How it was verified

Describe how a reviewer can confirm this works.

```bash
python3 -m pytest -q tests
python3 -m coverage run -m pytest -q tests && python3 -m coverage report
ruff check ragghost tests
python3 -m ragghost check .        # must exit 0 -- the tool holds itself to its own standard
```

## Checklist

- [ ] The runtime stays dependency-free (standard library only); any new dependency is dev/test-only.
- [ ] New behaviour is covered by tests that assert real output on a known input (no vacuous tests).
- [ ] A new detector has both a must-fire case and a must-stay-quiet look-alike.
- [ ] `ruff check`, the test suite, and `python3 -m ragghost check .` all pass locally.
- [ ] `CHANGELOG.md` is updated under `[Unreleased]`.
- [ ] Status claims (the README table) are updated in this same PR, if applicable.
