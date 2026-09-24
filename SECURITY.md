# Security Policy

## Supported versions

rag-graph-surgeon is at an early `0.1.x`. Security fixes are applied to the latest release on the
`main` branch; there are no separate maintenance branches yet.

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Reporting a vulnerability

Please report suspected vulnerabilities **privately**, not in a public issue.

- Preferred: open a private report through GitHub's
  [Security Advisories](https://github.com/Cshearer210/rag-graph-surgeon/security/advisories/new)
  ("Report a vulnerability") on this repository.

When you report, please include:

- the version or commit you were running,
- the platform and Python version,
- steps to reproduce, and the impact you observed or expect.

You can expect an acknowledgement within a few days. Once a fix is prepared, a patched release is
published and the advisory is disclosed with credit to the reporter, unless you ask to remain
anonymous.

## Scope notes

This tool has **no runtime dependencies** and **never accesses the network**. Every stage except
`fix` is read-only. `fix` writes only when `--apply` is passed, touches only the deterministic,
reversible class of changes, and re-measures after each edit — rolling the change back if the
defect is not actually gone. The most relevant classes of report are therefore around file handling
of an untrusted target tree (path traversal, symlink handling, resource use on a hostile directory
layout).
