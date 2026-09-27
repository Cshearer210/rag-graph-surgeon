# CALLED BY: pytest -- extra coverage for stage 4 (RETRIEVE).
# FIRES WHEN: asked.
"""Query ranking, indexing boundaries, the self-audit, and every report branch of retrieve.py."""
import io


import pytest

from ragghost import ranks_meaning
from ragghost.retrieve import build_index, Retriever, _tokens, _MAX_BYTES


# ── the noise probe must be VERIFIED ABSENT, not merely drawn at random ──────
#
# ⛔ THE REGRESSION THIS GUARDS, measured 2026-09-27 by running `ragghost check .` ten times on an
# unchanged tree: ONE run in ten reported `RETR-BLIND, noise scored 0.175`. The probe had just been
# changed from a hardcoded literal (which carried a `while noise in self.index` loop guaranteeing
# absence) to a random `wordlike` draw, and a short syllable like `wose` or `tico` can genuinely be
# a token in a real corpus. So the probe was USUALLY absent and not RELIABLY absent.
#
# ⭐ A CHECK THAT GIVES TWO ANSWERS ABOUT ONE UNCHANGED TREE IS WORSE THAN A WRONG ONE: nobody can
# tell which run to believe, and it teaches a reader to re-run a real finding away.

def test_the_noise_probe_is_absent_from_the_index_every_time(tree):
    """Run the audit many times over one corpus. Every probe must score exactly zero."""
    d = tree({
        "a.py": "def wose():\n    return 'tico duse wuda'\n",
        "b.py": "import a\n\nVALUE = a.wose()\n",
        "notes.md": "wose tico duse wuda cewe vohe teha mehe vepo sifo\n",
    })
    for _ in range(40):
        r = build_index(d)
        assert r.audit_noise is not None, "an absent probe was constructible here"
        probe, score = r.audit_noise
        assert score == 0.0, "probe %r scored %.4f -- it was not absent from the corpus" % (
            probe, score)
        assert r.exit_code() == 0, "a healthy retriever must be clean on EVERY run, not most"


def test_a_probe_whose_token_is_in_the_corpus_is_redrawn(tree, monkeypatch):
    """Force the collision: the first draw is a term the corpus definitely has."""
    d = tree({"a.py": "PLANTED = 'collide'\n", "b.py": "import a\n"})
    draws = ["collide", "collide", "zzqunlikelyword qqxunlikelyword"]

    def fake(n=12, shape="hex", seed=None):
        return [draws.pop(0)] if draws else ["qqfallbackword"]

    monkeypatch.setattr(ranks_meaning, "gibberish", fake)
    r = build_index(d)
    assert r.audit_noise is not None
    assert "collide" not in r.audit_noise[0], "a colliding probe must be redrawn, not used"
    assert r.audit_noise[1] == 0.0


def test_no_absent_probe_at_all_is_UNKNOWN_never_clean_and_never_a_finding(tree, monkeypatch):
    """⛔ If every draw collides, there is nothing to compare against. That is exit 2 -- not 0
    (which would be a clean bill of health nobody measured) and not 1 (which would be a finding
    invented out of the tool's own inability to build a probe)."""
    d = tree({"a.py": "PLANTED = 'collide'\n", "b.py": "import a\n"})
    monkeypatch.setattr(ranks_meaning, "gibberish", lambda n=12, shape="hex", seed=None: ["collide"])
    r = build_index(d)
    assert r.audit_noise is None
    assert r.exit_code() == 2

    buf = io.StringIO()
    r.report(out=buf)
    text = buf.getvalue()
    assert "UNKNOWN" in text and "absent" in text, \
        "the report must say it could not build a probe, not stay silent about it"


# ── the tokeniser ───────────────────────────────────────────────────────────
def test_tokens_lowercases_and_splits():
    assert _tokens("Hello World_x foo123") == ["hello", "world_x", "foo123"]


def test_tokens_drops_single_chars_and_punctuation():
    # the token regex requires at least two chars
    assert _tokens("a bb ccc . , ! -") == ["bb", "ccc"]


# ── query() ─────────────────────────────────────────────────────────────────
def test_query_empty_string_returns_nothing(tree):
    d = tree({"a.md": "alpha beta gamma\n"})
    assert build_index(d).query("") == []


def test_query_unknown_term_returns_nothing(tree):
    d = tree({"a.md": "alpha beta gamma\n"})
    assert build_index(d).query("nonexistentterm") == []


def test_query_on_empty_index_returns_nothing():
    r = Retriever()
    assert r.query("anything") == []


def test_distinctive_term_ranks_its_own_file_first(tree):
    d = tree({
        "extraction.md": "winterization decarboxylation solvent\n",
        "growing.md": "germination soil nutrients harvest\n",
    })
    r = build_index(d)
    hits = r.query("decarboxylation")
    assert hits
    assert hits[0][0] == "extraction.md"


def test_query_respects_k_limit(tree):
    files = {("f%d.md" % i): "sharedterm unique%d\n" % i for i in range(6)}
    d = tree(files)
    r = build_index(d)
    assert len(r.query("sharedterm", k=3)) == 3


# ── indexing boundaries ─────────────────────────────────────────────────────
def test_binary_and_unknown_extensions_are_not_indexed(tree):
    d = tree({"a.md": "realword here\n", "img.png": "not text", "v.mp4": "binary"})
    r = build_index(d)
    assert "a.md" in r.docs
    assert "img.png" not in r.docs and "v.mp4" not in r.docs


def test_files_over_the_size_cap_are_skipped(tree):
    big = "word " * (_MAX_BYTES // 3)      # comfortably over the byte cap
    d = tree({"huge.md": big, "small.md": "tiny content\n"})
    r = build_index(d)
    assert "small.md" in r.docs
    assert "huge.md" not in r.docs


def test_empty_files_are_not_indexed(tree):
    d = tree({"empty.md": "", "real.md": "content here\n"})
    r = build_index(d)
    assert "empty.md" not in r.docs
    assert "real.md" in r.docs


def test_ndocs_counts_indexed_documents(tree):
    d = tree({"a.md": "one two\n", "b.py": "three four\n"})
    assert build_index(d).ndocs == 2


# ── the self-audit ──────────────────────────────────────────────────────────
def test_audit_present_probe_finds_a_unique_term(tree):
    d = tree({"a.md": "alphaunique wordone\n", "b.md": "betaunique wordtwo\n"})
    r = build_index(d)
    assert r.audit_present is not None
    term, expected, got = r.audit_present
    assert got is True


def test_audit_noise_probe_scores_zero_on_a_healthy_index(tree):
    d = tree({"a.md": "alpha beta gamma delta\n"})
    r = build_index(d)
    assert r.audit_noise[1] == 0.0


def test_exit_code_clean(tree):
    d = tree({"a.md": "alphaunique one\n", "b.md": "betaunique two\n"})
    assert build_index(d).exit_code() == 0


def test_exit_code_unknown_on_empty():
    assert Retriever().exit_code() == 2


def test_exit_code_flags_blind_retriever():
    r = Retriever()
    r.ndocs = 3
    r.audit_present = ("term", "a.md", False)   # indexed a term but cannot find it
    r.audit_noise = ("noise", 0.0)
    assert r.exit_code() == 1


def test_exit_code_flags_noise_ranking():
    r = Retriever()
    r.ndocs = 3
    r.audit_present = ("term", "a.md", True)
    r.audit_noise = ("noise", 0.5)              # gibberish scored above zero
    assert r.exit_code() == 1


def test_exit_code_unknown_when_no_present_probe():
    r = Retriever()
    r.ndocs = 3
    r.audit_present = None
    assert r.exit_code() == 2


# ── report() branches ───────────────────────────────────────────────────────
def test_report_clean_corpus(tree):
    d = tree({"a.md": "alphaunique one\n", "b.md": "betaunique two\n"})
    buf = io.StringIO()
    build_index(d).report(buf)
    text = buf.getvalue()
    assert "AUDITED AGAINST ITS OWN CORPUS" in text
    assert "PRESENT PROBE" in text
    assert "NOISE PROBE" in text


def test_report_empty_is_unknown():
    r = Retriever()
    r.root = "/x"
    buf = io.StringIO()
    r.report(buf)
    assert "NOTHING INDEXED" in buf.getvalue()


def test_report_flags_blind():
    r = Retriever()
    r.root = "/x"
    r.ndocs = 2
    r.index = {"term": {"a.md": 1}}
    r.docs = {"a.md": 1}
    r.audit_present = ("term", "a.md", False)
    r.audit_noise = ("noise", 0.0)
    buf = io.StringIO()
    r.report(buf)
    assert "BLIND" in buf.getvalue()


def test_report_flags_noise():
    r = Retriever()
    r.root = "/x"
    r.ndocs = 2
    r.index = {"term": {"a.md": 1}}
    r.docs = {"a.md": 1}
    r.audit_present = ("term", "a.md", True)
    r.audit_noise = ("noise", 0.7)
    buf = io.StringIO()
    r.report(buf)
    assert "RANKS NOISE" in buf.getvalue()


def test_report_says_unknown_when_no_present_probe():
    r = Retriever()
    r.root = "/x"
    r.ndocs = 2
    r.index = {"a": {"x.md": 1}}
    r.docs = {"x.md": 1}
    r.audit_present = None
    r.audit_noise = ("noise", 0.0)
    buf = io.StringIO()
    r.report(buf)
    assert "could not build one" in buf.getvalue()
