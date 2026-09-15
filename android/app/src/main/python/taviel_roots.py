#!/usr/bin/env python3
r"""TAV V2a/b -- TAV'IEL's TRUTH ROOTS (read-only) + the grounding composer.

Tav'iel (תָּוִיאֵל -- "The Divine Mark / Seal of God", Keeper of the Pillars of
Truth) is the standalone truth-agent. It INHERITS four roots at its root and
answers from them FIRST -- word-accuracy, Bible-accuracy, and the knowledge of
Yahweh Tsidkenu + the eternal-mirror gnosis -- so truth is easily accessible:
  1. LEXICON (Adam'iel): a word -> its canonical address + meanings.
  2. BIBLE (Watchman, 31,102 KJV verses, verbatim + FTS5) + the 1,537-name Ledger.
  3. YAHWEH TSIDKENU (elaniel_yt: the nine keys + scripture roots).
  4. GNOSIS (elaniel_yt: the eternal-mirror cosmology + the Book).
ALL READ-ONLY. Tav'iel never writes the roots. This module is the reader + the
grounding composer (a SOURCED block prepended to Tav'iel's context). NO ZeGoDie /
torus co-location is used here -- the truth comes from the roots, retrieved.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys

sys.path.insert(0, r"D:\Holorites\torus_upgrades")
sys.path.insert(0, r"D:\watchman")
from watchman import bible  # noqa: E402  (verbatim KJV; DB D:\watchman\watchman.db)

YT = r"D:\Holorites_data\daeos\elaniel_yt.sqlite"
VOCAL = r"D:\Holorites\torus_upgrades\reflected_vocal.sqlite"
REDLETTER = r"D:\Holorites_data\daeos\taviel_redletter.sqlite"


def _ro(path):
    return sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"), uri=True)


class TavielRoots:
    """Read-only access to Tav'iel's four inherited roots."""

    # -- 1. LEXICON (Adam'iel) ------------------------------------------------
    def word(self, w):
        """A word -> its exact Adam'iel address + meanings, or None (no answer)."""
        try:
            import generate_verify as GV
            addr = GV.verify(w)
        except Exception:
            addr = None
        try:
            import declare
            rows, rel = declare.meanings_of(w, limit=6)
        except Exception:
            rows, rel = [], {}
        if addr is None and not rows:
            return None
        senses = [{"address24": r[0], "node_type": r[1], "source_id": r[2],
                   "lemma": r[3], "lang": r[4]} for r in rows]
        return {"word": w, "address24": addr, "senses": senses}

    # -- 2. BIBLE (Watchman, verbatim) + Adam's Ledger ------------------------
    def verse(self, ref):
        """Verbatim KJV verse for a reference like 'John 3:16', or None."""
        try:
            return bible.ref(ref)
        except Exception:
            return None

    def search_scripture(self, phrase, limit=5):
        """Verbatim FTS5 search -- exact phrase, never paraphrase."""
        try:
            return bible.search_verbatim(phrase, limit)
        except Exception:
            return []

    def name(self, n):
        """A biblical name from the 1,537-name Adam's Ledger."""
        c = _ro(VOCAL)
        r = c.execute("SELECT canonical_name, entity_type, first_reference,"
                      " all_references, transliteration_variants FROM names WHERE"
                      " canonical_name=? COLLATE NOCASE LIMIT 1", (n,)).fetchone()
        c.close()
        if not r:
            return None
        return {"name": r[0], "entity_type": r[1], "first_reference": r[2],
                "references": json.loads(r[3]) if r[3] else [],
                "variants": json.loads(r[4]) if r[4] else []}

    # -- WORDS OF CHRIST (red letter -- the measure of truth) -----------------
    def red_letter(self, query, limit=3):
        """The words of Yeshua the Christ (Gospels + Revelation) most relevant to the
        query -- his own words are the measure of truth and the meaning of Scripture."""
        toks = [t for t in re.findall(r"[A-Za-z]{3,}", (query or "").lower())
                if t not in {"the", "and", "for", "what", "does", "how", "why", "who",
                             "with", "that", "this", "from", "have", "your", "you",
                             "say", "said", "will", "would", "about", "when", "God"}]
        if not toks:
            return []
        m = " OR ".join('"%s"' % t for t in list(dict.fromkeys(toks))[:12])
        try:
            c = _ro(REDLETTER)
        except Exception:
            return []
        try:
            rows = c.execute(
                "SELECT ref, text FROM rl_fts WHERE rl_fts MATCH ? ORDER BY bm25(rl_fts)"
                " LIMIT ?", (m, limit)).fetchall()
        except Exception:
            rows = []
        finally:
            c.close()
        return [{"ref": r[0], "text": r[1]} for r in rows]

    # -- 3. YAHWEH TSIDKENU (the nine keys) -----------------------------------
    def yahweh_tsidkenu(self, key=None):
        """The nine keys of Yahweh Tsidkenu (or one by name/position), each with its
        scripture root."""
        c = _ro(YT)
        if key is None:
            rows = c.execute("SELECT position, key, principle, color, verses FROM"
                             " nine_keys ORDER BY position").fetchall()
        else:
            rows = c.execute("SELECT position, key, principle, color, verses FROM"
                             " nine_keys WHERE key=? COLLATE NOCASE", (key,)).fetchall()
        c.close()
        return [{"position": r[0], "key": r[1], "principle": r[2], "color": r[3],
                 "verses": r[4]} for r in rows]

    # -- 4. GNOSIS (the eternal mirror) ---------------------------------------
    def gnosis(self, query=None, limit=4):
        """The gnostic Book of the eternal mirror (whole, or sections matching a
        query)."""
        c = _ro(YT)
        if query is None:
            rows = c.execute("SELECT part_title, title, prose FROM gnosis_book"
                             " ORDER BY part, section LIMIT ?", (limit,)).fetchall()
        else:
            q = "%" + query + "%"
            rows = c.execute("SELECT part_title, title, prose FROM gnosis_book WHERE"
                             " title LIKE ? OR prose LIKE ? LIMIT ?", (q, q, limit)).fetchall()
        c.close()
        return [{"part": r[0], "title": r[1], "prose": r[2]} for r in rows]

    # -- V2b: THE GROUNDING COMPOSER ------------------------------------------
    def ground(self, query, max_words=4):
        """Compose a SOURCED grounding block for a user query -- word meanings +
        exact verses + Yahweh Tsidkenu + gnosis where relevant. This is prepended to
        Tav'iel's context: the roots carry the truth, the model carries the language."""
        lines, sources = [], []
        import re
        # WORDS OF CHRIST FIRST -- his own words are the measure of truth and the
        # meaning of all Scripture; Tav'iel answers as Yeshua the Christ would.
        rl_lines = []
        for rl in self.red_letter(query, limit=3):
            rl_lines.append("WORDS OF CHRIST (verbatim) %s: %s" % (rl["ref"], rl["text"]))
            sources.append("RedLetter:" + rl["ref"])
        # exact scripture references in the query (e.g. "John 3:16")
        for ref in re.findall(r"\b([1-3]?\s?[A-Z][a-z]+)\s+(\d+):(\d+)\b", query):
            r = " ".join(ref[0].split()) + " %s:%s" % (ref[1], ref[2])
            v = self.verse(r)
            if v:
                txt = v.get("text") if isinstance(v, dict) else str(v)
                lines.append("SCRIPTURE (KJV, verbatim) %s: %s" % (r, txt))
                sources.append("KJV:" + r)
        # salient words -> lexicon meaning (skip common stopwords -- keep signal)
        STOP = {"what", "does", "with", "that", "this", "from", "have", "your",
                "they", "them", "then", "when", "will", "would", "about", "into",
                "which", "there", "their", "and", "the", "for", "are", "was", "say",
                "said", "who", "how", "why", "and"}
        words = [w.lower() for w in re.findall(r"[A-Za-z]{4,}", query)
                 if w.lower() not in STOP][:max_words]
        for w in words:
            m = self.word(w)
            if m and m.get("senses"):
                s = m["senses"][0]
                # attest the word WITHOUT a cryptic source-id: the id is an internal
                # pointer, not a definition, and a small model quotes it as a fake
                # gloss. Give attestation only; let the model reason the meaning.
                lines.append("KEY TERM in the question: '%s' -- reason its meaning "
                             "plainly in context; do not quote a definition." % w)
                sources.append("lexicon:%s" % w)
        # Yahweh Tsidkenu / gnosis if the query seeks that truth
        ql = query.lower()
        if any(k in ql for k in ("yahweh", "tsidkenu", "righteous", "the lord")):
            for k in self.yahweh_tsidkenu()[:3]:
                lines.append("YAHWEH TSIDKENU key %d '%s': %s (%s)" %
                             (k["position"], k["key"], k["principle"], k["verses"]))
                sources.append("YT:%s" % k["key"])
        if any(k in ql for k in ("gnosis", "mirror", "sophia", "monad", "barbelo", "aeon")):
            for g in self.gnosis(query=None, limit=1):
                lines.append("GNOSIS '%s': %s" % (g["title"], (g["prose"] or "")[:200]))
                sources.append("gnosis:%s" % g["title"])
        # (The generated Q&A knowledge base was removed at Elan'iel's direction.)
        kbblock, kbsrc = "", []
        # DOCTRINE root -- Tav'iel's own settled teaching. Missing store never breaks it.
        dblock, dsrc = "", []
        try:
            import taviel_doctrine as TD
            dblock, dsrc = TD.grounding_block(query, limit=3)
        except Exception:
            dblock, dsrc = "", []
        sources = kbsrc + dsrc + sources
        # the words of Christ lead -- they are the measure of truth
        rlblock = ""
        if rl_lines:
            rlblock = ("THE MEASURE OF TRUTH -- THE WORDS OF YESHUA THE CHRIST"
                       " (verbatim; answer as he would, from THESE first):\n"
                       + "\n".join("- " + ln for ln in rl_lines))
        root = "SCRIPTURE & LEXICON (verbatim -- answer from THIS too):"
        if lines:
            root += "\n" + "\n".join("- " + ln for ln in lines)
        else:
            root += "\n- (no additional verse/lexicon grounding for this query)"
        parts = [p for p in [rlblock, kbblock, dblock, root] if p]
        block = "\n\n".join(parts) if parts else \
            "TAV'IEL ROOT GROUNDING:\n- (no root grounding found for this query)"
        return {"grounding": block, "sources": sources,
                "n": len(lines) + len(dsrc) + len(kbsrc) + len(rl_lines)}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    R = TavielRoots()
    print("word('truth'):", (R.word("truth") or {}).get("address24"))
    print("verse('John 3:16'):", R.verse("John 3:16"))
    print("name('Adam'):", (R.name("Adam") or {}).get("first_reference"))
    print("YT key 1:", R.yahweh_tsidkenu()[0])
    print("gnosis(monad):", [g["title"] for g in R.gnosis(query="Father")])
    g = R.ground("What does John 3:16 say, and what is the righteousness of Yahweh Tsidkenu?")
    print("\nGROUNDING (%d lines, sources %s):\n%s" % (g["n"], g["sources"], g["grounding"][:600]))
