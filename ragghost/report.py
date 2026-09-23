# CALLED BY: ragghost/__main__.py  (`python3 -m ragghost check <path> --format json|sarif|text`)
# FIRES WHEN: asked -- the machine-readable + configurable face of the tool.
"""One finding model, three output formats, and the two things a checker needs to be adopted:
a config that says which checks run, and an inline comment that silences one on a single file.

Every stage already produces findings; PLAN already ranks them. This turns that ranked list into
a stable, coded, filterable report a CI job can consume:

    codes           each finding carries a short stable CODE (GRAPH-ORPHAN, ORG-MISFILED, ...)
    config          .ragghost.json in the target root: {"select": [...], "ignore": [...]}
    suppression     a line `# ragghost: allow GRAPH-ORPHAN` in a file drops that file's finding
    formats         text (human), json (a script), sarif (GitHub code scanning / a dashboard)

No dependencies. Reads the target; never writes to it.
"""
from __future__ import annotations

import json
import os
import re
import sys

from .plan import plan, SEV

__all__ = ["collect", "Finding", "to_text", "to_json", "to_sarif", "check", "KIND_TO_CODE"]

# a stable code per finding kind -- the vocabulary a config selects/ignores by
KIND_TO_CODE = {
    "scan": "SCAN-DRIFT",
    "moved-ref": "GRAPH-DANGLING",
    "orphan": "GRAPH-ORPHAN",
    "retrieval": "RETR-BLIND",
    "no-gate": "HARNESS-NOGATE",
    "misfiled": "ORG-MISFILED",
}
_SEV_SARIF = {"CRITICAL": "error", "HIGH": "error", "MEDIUM": "warning", "LOW": "note"}
_PATH_RE = re.compile(r"([\w./\-]+\.[A-Za-z0-9]{1,6})")


class Finding:
    __slots__ = ("code", "severity", "message", "detail", "path", "line")

    def __init__(self, code, severity, message, detail, path=None, line=None):
        self.code = code
        self.severity = severity
        self.message = message
        self.detail = detail
        self.path = path
        self.line = line

    def to_dict(self):
        return {"code": self.code, "severity": self.severity, "message": self.message,
                "detail": self.detail, "path": self.path, "line": self.line}


def _guess_path(target, root):
    """Best-effort: the first path-like token in a finding's target that exists under root."""
    for m in _PATH_RE.finditer(target or ""):
        tok = m.group(1)
        if os.path.exists(os.path.join(root, tok)):
            return tok
    m = _PATH_RE.search(target or "")
    return m.group(1) if m else None


def _load_config(root):
    """{"select": [...codes/kinds...], "ignore": [...]} from .ragghost.json, if present."""
    p = os.path.join(root, ".ragghost.json")
    if not os.path.exists(p):
        return {"select": None, "ignore": set()}
    try:
        with open(p, encoding="utf-8") as f:
            cfg = json.load(f)
        sel = cfg.get("select")
        return {"select": set(sel) if sel else None, "ignore": set(cfg.get("ignore") or [])}
    except (OSError, ValueError):
        return {"select": None, "ignore": set()}   # a broken config never silently drops findings


def _suppressed_inline(finding, root):
    """True if the finding's own file carries `# ragghost: allow <CODE>` (or a bare allow)."""
    if not finding.path:
        return False
    ap = os.path.join(root, finding.path)
    if not os.path.exists(ap) or os.path.isdir(ap):
        return False
    try:
        with open(ap, encoding="utf-8", errors="replace") as f:
            head = f.read(4000)
    except OSError:
        return False
    pat = re.compile(r"#\s*ragghost:\s*(?:allow|ignore)\s+(%s|ALL)\b" % re.escape(finding.code), re.I)
    return bool(pat.search(head))


def collect(root):
    """Every finding, coded, from the real ranked plan. Reads only."""
    p = plan(root)
    out = []
    for sev, kind, target, action in p.items:
        code = KIND_TO_CODE.get(kind, kind.upper())
        out.append(Finding(code, sev, action, target, _guess_path(target, os.path.abspath(root))))
    return out


def _apply(findings, root):
    cfg = _load_config(root)
    kept = []
    for f in findings:
        keys = {f.code, f.code.split("-")[0]}
        if cfg["select"] is not None and not (keys & cfg["select"]):
            continue
        if keys & cfg["ignore"]:
            continue
        if _suppressed_inline(f, os.path.abspath(root)):
            continue
        kept.append(f)
    return kept


def to_text(findings, root):
    if not findings:
        return "CHECK  %s\n%s\n  Nothing found (after config + suppression).\n" % (root, "=" * 60)
    order = {k: i for i, k in enumerate(("CRITICAL", "HIGH", "MEDIUM", "LOW"))}
    findings = sorted(findings, key=lambda f: order.get(f.severity, 9))
    lines = ["CHECK  %s" % root, "=" * 60, "  %d finding(s)" % len(findings)]
    for f in findings:
        loc = ("  %s" % f.path) if f.path else ""
        lines.append("  [%-8s %-14s]%s  %s" % (f.severity, f.code, loc, f.message))
        lines.append("      %s" % f.detail)
    return "\n".join(lines) + "\n"


def to_json(findings, root):
    return json.dumps({"tool": "rag-ghost", "root": os.path.abspath(root),
                       "findings": [f.to_dict() for f in findings]}, indent=2) + "\n"


def to_sarif(findings, root):
    rules, results = {}, []
    for f in findings:
        rules.setdefault(f.code, {"id": f.code, "name": f.code,
                                  "shortDescription": {"text": f.code}})
        loc = {"physicalLocation": {"artifactLocation": {"uri": f.path or "unknown"}}}
        results.append({"ruleId": f.code, "level": _SEV_SARIF.get(f.severity, "warning"),
                        "message": {"text": "%s -- %s" % (f.message, f.detail)},
                        "locations": [loc]})
    doc = {"$schema": "https://json.schemastore.org/sarif-2.1.0.json", "version": "2.1.0",
           "runs": [{"tool": {"driver": {"name": "rag-ghost", "rules": list(rules.values())}},
                     "results": results}]}
    return json.dumps(doc, indent=2) + "\n"


class _CheckResult:
    def __init__(self, findings, root, fmt):
        self.findings = findings
        self.root = root
        self.fmt = fmt

    def exit_code(self):
        return 1 if self.findings else 0

    def report(self, out=sys.stdout):
        if self.fmt == "json":
            out.write(to_json(self.findings, self.root))
        elif self.fmt == "sarif":
            out.write(to_sarif(self.findings, self.root))
        else:
            out.write(to_text(self.findings, self.root))


def check(root, fmt="text", extra_findings=None):
    """The one command CI runs: built-in findings + any plugin findings, filtered, in one format."""
    findings = _apply(collect(root) + list(extra_findings or []), root)
    return _CheckResult(findings, root, fmt)
