# CALLED BY: pytest -- extra coverage for stage 4 (RETRIEVE).
# FIRES WHEN: asked.
"""Query ranking, indexing boundaries, the self-audit, and every report branch of retrieve.py."""
import io


from ragghost.retrieve import build_index, Retriever, _tokens, _MAX_BYTES


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
