---
name: Feature request
about: Suggest a new detector or capability
title: "[feature] "
labels: enhancement
assignees: ''
---

## The problem

What silent or hidden failure would this catch? Describe the real situation where a system looks
fine but is not — the kind of thing this tool exists to surface.

## Proposed detector or capability

What should the tool do? If it is a new check, say what would make it **fire** and, just as
importantly, what look-alike it must stay **quiet** on (so it does not cry wolf).

## Which stage

Is this an extension of an existing stage (SCAN, GRAPH, ORGANIZE, RETRIEVE, HARNESS, PLAN, ANALYSE,
FIX), a new stage, or a plugin?

## Constraints to respect

- The runtime must stay dependency-free (standard library only) and offline.
- Every finding must carry its denominator, and populations are discovered, not typed.
- Three outcomes: `0` clean · `1` found something · `2` could-not-tell.

## Alternatives considered

Anything you have tried, or existing tools that do part of this.
