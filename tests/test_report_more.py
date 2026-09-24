# CALLED BY: pytest -- extra coverage for the reporting/config/suppression layer.
# FIRES WHEN: asked.
"""Finding model, the three formats, config loading, and inline suppression -- edge cases."""
import io
import json


from ragghost.report import (Finding, to_text, to_json, to_sarif, check, collect,
                            _guess_path, _load_config, _suppressed_inline, _CheckResult,
                            KIND_TO_CODE)


BROKEN = {
    "reports/__init__.py": "", "reports/exporter.py": "def e(): return 1\n",
    "tests/test_x.py": "def test(): assert True\n",
}


# ── the Finding model ───────────────────────────────────────────────────────
def test_finding_to_dict_roundtrips_fields():
    f = Finding("GRAPH-ORPHAN", "MEDIUM", "msg", "detail", "a/b.py", 12)
    d = f.to_dict()
    assert d == {"code": "GRAPH-ORPHAN", "severity": "MEDIUM", "message": "msg",
                 "detail": "detail", "path": "a/b.py", "line": 12}


def test_kind_to_code_vocabulary():
    assert KIND_TO_CODE["orphan"] == "GRAPH-ORPHAN"
    assert KIND_TO_CODE["moved-ref"] == "GRAPH-DANGLING"
    assert KIND_TO_CODE["misfiled"] == "ORG-MISFILED"


# ── to_text ─────────────────────────────────────────────────────────────────
def test_to_text_empty_says_nothing_found():
    out = to_text([], "/root")
    assert "Nothing found" in out


def test_to_text_lists_findings_sorted_by_severity():
    findings = [
        Finding("HARNESS-NOGATE", "HIGH", "high msg", "d1"),
        Finding("SCAN-DRIFT", "CRITICAL", "crit msg", "d2"),
    ]
    out = to_text(findings, "/root")
    assert out.index("crit msg") < out.index("high msg")   # CRITICAL printed first


# ── to_json / to_sarif shapes ───────────────────────────────────────────────
def test_to_json_is_valid_and_carries_findings():
    findings = [Finding("GRAPH-ORPHAN", "MEDIUM", "m", "d", "a.py")]
    doc = json.loads(to_json(findings, "/root"))
    assert doc["tool"] == "rag-ghost"
    assert doc["findings"][0]["code"] == "GRAPH-ORPHAN"


def test_to_sarif_has_rules_and_results():
    findings = [Finding("GRAPH-ORPHAN", "MEDIUM", "m", "d", "a.py"),
                Finding("SCAN-DRIFT", "CRITICAL", "m2", "d2", "b.py")]
    doc = json.loads(to_sarif(findings, "/root"))
    run = doc["runs"][0]
    assert run["tool"]["driver"]["name"] == "rag-ghost"
    assert len(run["results"]) == 2
    codes = {r["ruleId"] for r in run["results"]}
    assert codes == {"GRAPH-ORPHAN", "SCAN-DRIFT"}


def test_to_sarif_maps_severity_to_level():
    findings = [Finding("X", "CRITICAL", "m", "d"), Finding("Y", "LOW", "m", "d")]
    doc = json.loads(to_sarif(findings, "/root"))
    levels = {r["ruleId"]: r["level"] for r in doc["runs"][0]["results"]}
    assert levels["X"] == "error"
    assert levels["Y"] == "note"


# ── _guess_path ─────────────────────────────────────────────────────────────
def test_guess_path_prefers_an_existing_file(tree):
    d = tree({"real.py": "X=1\n"})
    assert _guess_path("something real.py here", d) == "real.py"


def test_guess_path_falls_back_to_first_pathish_token(tree, tmp_path):
    got = _guess_path("names gone.py which is missing", str(tmp_path))
    assert got == "gone.py"


def test_guess_path_none_when_no_token(tree, tmp_path):
    assert _guess_path("no paths at all", str(tmp_path)) is None


def test_guess_path_none_on_empty_target(tmp_path):
    assert _guess_path("", str(tmp_path)) is None


# ── _load_config ────────────────────────────────────────────────────────────
def test_load_config_missing_returns_defaults(tmp_path):
    cfg = _load_config(str(tmp_path))
    assert cfg["select"] is None
    assert cfg["ignore"] == set()


def test_load_config_reads_select_and_ignore(tree):
    d = tree({".ragghost.json": json.dumps({"select": ["GRAPH"], "ignore": ["ORG-MISFILED"]})})
    cfg = _load_config(d)
    assert cfg["select"] == {"GRAPH"}
    assert cfg["ignore"] == {"ORG-MISFILED"}


def test_broken_config_never_silently_drops_findings(tree):
    d = tree({".ragghost.json": "{not valid json"})
    cfg = _load_config(d)
    assert cfg["select"] is None      # a broken config selects everything, ignores nothing
    assert cfg["ignore"] == set()


# ── _suppressed_inline ──────────────────────────────────────────────────────
def test_suppression_none_path_is_not_suppressed(tmp_path):
    f = Finding("GRAPH-ORPHAN", "MEDIUM", "m", "d", None)
    assert _suppressed_inline(f, str(tmp_path)) is False


def test_suppression_missing_file_is_not_suppressed(tmp_path):
    f = Finding("GRAPH-ORPHAN", "MEDIUM", "m", "d", "gone.py")
    assert _suppressed_inline(f, str(tmp_path)) is False


def test_suppression_directory_is_not_suppressed(tree):
    d = tree({"pkg/__init__.py": ""})
    f = Finding("GRAPH-ORPHAN", "MEDIUM", "m", "d", "pkg")
    assert _suppressed_inline(f, d) is False


def test_inline_allow_specific_code(tree):
    d = tree({"a.py": "# ragghost: allow GRAPH-ORPHAN\nX=1\n"})
    f = Finding("GRAPH-ORPHAN", "MEDIUM", "m", "d", "a.py")
    assert _suppressed_inline(f, d) is True


def test_inline_allow_all(tree):
    d = tree({"a.py": "# ragghost: allow ALL\nX=1\n"})
    f = Finding("GRAPH-ORPHAN", "MEDIUM", "m", "d", "a.py")
    assert _suppressed_inline(f, d) is True


def test_inline_allow_wrong_code_does_not_suppress(tree):
    d = tree({"a.py": "# ragghost: allow HARNESS-NOGATE\nX=1\n"})
    f = Finding("GRAPH-ORPHAN", "MEDIUM", "m", "d", "a.py")
    assert _suppressed_inline(f, d) is False


# ── collect() and check() end to end ────────────────────────────────────────
def test_collect_codes_every_finding(tree):
    d = tree(BROKEN)
    findings = collect(d)
    assert findings
    assert all(f.code for f in findings)


def test_check_json_format(tree):
    d = tree(BROKEN)
    result = check(d, fmt="json")
    buf = io.StringIO()
    result.report(buf)
    doc = json.loads(buf.getvalue())
    assert doc["tool"] == "rag-ghost"


def test_check_sarif_format(tree):
    d = tree(BROKEN)
    buf = io.StringIO()
    check(d, fmt="sarif").report(buf)
    assert "sarif" in buf.getvalue().lower()


def test_check_config_ignore_drops_a_code(tree):
    files = dict(BROKEN)
    files[".ragghost.json"] = json.dumps({"ignore": ["GRAPH-ORPHAN"]})
    d = tree(files)
    codes = {f.code for f in check(d).findings}
    assert "GRAPH-ORPHAN" not in codes


def test_check_extra_findings_are_included(tree):
    d = tree(BROKEN)
    extra = [Finding("PLUGIN-X", "HIGH", "from a plugin", "detail", "a.py")]
    result = check(d, extra_findings=extra)
    assert any(f.code == "PLUGIN-X" for f in result.findings)


def test_checkresult_exit_code():
    assert _CheckResult([], "/r", "text").exit_code() == 0
    assert _CheckResult([Finding("X", "LOW", "m", "d")], "/r", "text").exit_code() == 1
