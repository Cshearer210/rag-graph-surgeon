# CALLED BY: ragghost/__main__.py  (`python3 -m ragghost retrieve <path> [query]`)
# FIRES WHEN: asked -- a library module of a standalone tool, run by whoever downloaded it.
"""STAGE 4 -- RETRIEVE. Build a retrieval layer over the system, and AUDIT that it works.

⛔ THE FAILURE THIS STAGE EXISTS FOR: a retrieval layer that returns nothing looks exactly like a
system that contains nothing, and a retriever that ranks noise above real content "works" because
it returned something. Both are silent. So this stage does two things that must not be separated:
it builds an offline keyword retriever over the corpus, and then it AUDITS that retriever against
the corpus itself --

  PRESENT PROBE: a term that appears in exactly one file MUST retrieve that file. A retriever that
                 cannot find a term it indexed is blind, and a blind retriever reports an empty
                 world as confidently as a real one.
  NOISE PROBE:   a token generated to be absent MUST score ~0. If gibberish scores as high as a
                 real term, the ranking is meaningless and every later answer is untrustworthy.

No dependencies, no network, no model -- a stranger's checkout has none of those. Pure term
frequency over the text it already scanned. It reads; it never writes to the target.
"""
from __future__ import annotations

import math
import os
import re
import sys

from . import ranks_meaning
from .scan import KINDS, VENDORED

__all__ = ["build_index", "Retriever"]

_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,}")
_TEXT_KINDS = ("code", "config", "docs", "data", "web")
_TEXT_EXT = tuple(e for k in _TEXT_KINDS for e in KINDS[k])
_MAX_BYTES = 2_000_000        # do not read a giant file into memory; it is not indexable prose


def _tokens(text):
    return [t.lower() for t in _TOKEN.findall(text)]


class Retriever:
    """An offline keyword retriever, plus the verdict of auditing it against its own corpus."""

    def __init__(self):
        self.root = ""
        self.index = {}          # term -> {file: count}
        self.docs = {}           # file -> token count
        self.ndocs = 0
        self.audit_present = None   # (term, expected_file, got_it: bool)
        self.audit_noise = None     # (token, top_score: float)
        self.unreadable = 0

    def query(self, q, k=5):
        """Rank files for a query by tf-idf. Empty list when nothing matches -- not an error here,
        but the audit is what decides whether an empty result means 'absent' or 'blind'."""
        terms = _tokens(q)
        if not terms or not self.ndocs:
            return []
        scores = {}
        for term in terms:
            postings = self.index.get(term)
            if not postings:
                continue
            idf = math.log(1.0 + self.ndocs / len(postings))
            for f, tf in postings.items():
                scores[f] = scores.get(f, 0.0) + (tf / max(1, self.docs[f])) * idf
        return sorted(scores.items(), key=lambda kv: -kv[1])[:k]

    def audit(self):
        """Prove the retriever can find a present term and rejects an absent one. Fills the two
        audit_* fields. Derives its probes FROM the corpus, so it needs no external answer key."""
        # PRESENT PROBE: a term that appears in exactly one file, so the right answer is unambiguous.
        unique_term = None
        expected = None
        for term, postings in self.index.items():
            if len(postings) == 1 and len(term) >= 5:
                unique_term = term
                expected = next(iter(postings))
                break
        if unique_term is not None:
            hits = self.query(unique_term, k=3)
            got = any(f == expected for f, _ in hits)
            self.audit_present = (unique_term, expected, got)
        # NOISE PROBE: a token constructed to be absent from the index.
        #
        # ⛔ THIS USED TO BE A HARDCODED LITERAL -- `"zzq" + "x7q9w" * 3` -- and it was poisoned by
        # this very file. The token appeared in `retrieve.py`, `retrieve.py` is in the corpus
        # whenever you point this tool at its own repository, so the probe WAS in the index it was
        # meant to be absent from. A `while noise in self.index: noise += "q"` loop then quietly
        # mutated it until it was absent again, which meant the audit passed while measuring a
        # string nobody had written down. That is exactly the self-poisoning fixture
        # `ranks_meaning.gibberish()` was written to prevent, so the two are now ONE definition with
        # this as a reader rather than a second copy of the idea (nothing-ships-unwired 13-15).
        #
        # ⚠ `shape="wordlike"` IS REQUIRED HERE, not a preference. `_TOKEN` above matches
        # `[A-Za-z_][A-Za-z0-9_]+`, so a `hex` probe beginning with a digit would lose its first
        # character and a `punct` probe would be discarded entirely -- the probe would still be
        # absent from the corpus and the audit would still pass, while measuring a string this
        # function never constructed. `wordlike` is consonant-vowel pairs and always starts with a
        # letter.
        #
        # ⛔ AND THE PROBE IS VERIFIED ABSENT BEFORE IT IS USED, which the first version of this
        # delegation forgot -- a REGRESSION measured 2026-09-27 by running `ragghost check .` ten
        # times: ONE run in ten reported `RETR-BLIND, noise scored 0.175`. A `wordlike` syllable is
        # short (`wose`, `tico`, `duse`) and can genuinely occur as a token in a real corpus, so a
        # randomly drawn probe is USUALLY absent and not RELIABLY absent. The literal this replaced
        # carried that guarantee in a `while noise in self.index` loop, and delegating dropped it.
        #
        # ⭐ A CHECK THAT GIVES TWO DIFFERENT ANSWERS ABOUT ONE UNCHANGED TREE IS THE WORST DEFECT
        # AN AUDITING TOOL CAN HAVE -- worse than a wrong answer, because nobody can tell which run
        # to believe, and it turns a real finding into something a reader learns to re-run away.
        # So: draw, verify every token is absent, redraw if not, and if no absent probe can be found
        # at all say UNKNOWN rather than inventing a verdict.
        noise = None
        for _attempt in range(24):
            cand = ranks_meaning.gibberish(n=1, shape="wordlike")[0]
            if not any(t in self.index for t in _tokens(cand)):
                noise = cand
                break
        if noise is None:
            self.audit_noise = None          # exit_code() reads this as could-not-tell
            return
        top = self.query(noise, k=1)
        self.audit_noise = (noise, top[0][1] if top else 0.0)

    def exit_code(self):
        if not self.ndocs:
            return 2                                   # nothing indexed -> UNKNOWN
        if self.audit_present is None:
            return 2                                   # could not construct a present probe
        if self.audit_noise is None:
            return 2                                   # could not construct an ABSENT probe either
        _, _, got = self.audit_present
        _, noise_score = self.audit_noise
        if not got:
            return 1                                   # blind: cannot find a term it indexed
        if noise_score > 0.0:
            return 1                                   # ranks noise: absent token scored above zero
        return 0

    def report(self, out=sys.stdout):
        w = out.write
        w("RETRIEVE  %s\n" % self.root)
        w("=" * 70 + "\n")
        if not self.ndocs:
            w("  NOTHING INDEXED. UNKNOWN, not clean -- an empty index and an empty system\n"
              "  look identical, which is the failure this stage exists to tell apart.\n")
            return
        w("  indexed %d document(s), %d distinct term(s)\n" % (self.ndocs, len(self.index)))
        w("\n  THE RETRIEVER, AUDITED AGAINST ITS OWN CORPUS\n")
        if self.audit_present is None:
            w("    PRESENT PROBE: could not build one (no term is unique to a single file).\n"
              "    UNKNOWN -- the retriever's recall is unproven.\n")
        else:
            term, exp, got = self.audit_present
            mark = "OK" if got else "⛔ BLIND"
            w("    PRESENT PROBE: '%s' is unique to %s -> %s\n" % (term, exp, mark))
            if not got:
                w("      The retriever cannot find a term it indexed. It would report a full\n"
                  "      system as empty. Nothing built on it can be trusted.\n")
        if self.audit_noise is None:
            w("    NOISE PROBE:   could not construct one that is absent from this corpus.\n"
              "    UNKNOWN -- with no absent probe there is nothing to compare against, and a\n"
              "    guess here would be the confident wrong answer this stage exists to find.\n")
            return
        term, score = self.audit_noise
        mark = "OK" if score == 0.0 else "⛔ RANKS NOISE"
        w("    NOISE PROBE:   an absent token scored %.4f -> %s\n" % (score, mark))
        if score > 0.0:
            w("      Gibberish that is not in the corpus scored above zero. The ranking is\n"
              "      not meaningful and every answer it gives is suspect.\n")
        if self.exit_code() == 0:
            w("\n  The retrieval layer finds what it indexed and rejects what it did not. Safe\n"
              "  for later stages to ask questions of the system through it.\n")


def build_index(root, skip=VENDORED):
    """Build the retriever over `root`, then audit it. Reads only."""
    r = Retriever()
    r.root = os.path.abspath(root)
    skip = set(skip)
    for dirpath, dirnames, filenames in os.walk(r.root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in filenames:
            if not fn.lower().endswith(_TEXT_EXT):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, r.root).replace(os.sep, "/")
            try:
                if os.path.getsize(p) > _MAX_BYTES:
                    continue
                with open(p, encoding="utf-8", errors="replace") as f:
                    toks = _tokens(f.read())
            except OSError:
                r.unreadable += 1
                continue
            if not toks:
                continue
            r.docs[rel] = len(toks)
            counts = {}
            for t in toks:
                counts[t] = counts.get(t, 0) + 1
            for t, c in counts.items():
                r.index.setdefault(t, {})[rel] = c
    r.ndocs = len(r.docs)
    r.audit()
    return r
