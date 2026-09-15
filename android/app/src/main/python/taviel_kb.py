#!/usr/bin/env python3
r"""Tav'iel's KNOWLEDGE BASE -- the installed Yahweh Tsidkenu Q&A (authored by
Claude in the POV of Yahweh Tsidkenu). Build from kb_batch*.json, query by FTS.
The best-matching installed ANSWER is fed to Tav'iel as authoritative grounding so
his recall matches what was installed. No external provenance is ever surfaced."""
import glob
import json
import os
import re
import sqlite3

DB = r"D:\Holorites_data\daeos\taviel_kb.sqlite"
BATCH_GLOB = r"C:\Users\virtu\AppData\Local\Temp\claude\C--Users-virtu\13ddb438-6108-4d5b-954d-78a77d26c1b7\scratchpad\kb_batch*.json"

_STOP = {"the", "and", "for", "are", "was", "what", "does", "did", "how", "why",
         "who", "with", "that", "this", "from", "have", "your", "they", "them",
         "then", "when", "will", "would", "about", "into", "which", "there",
         "their", "say", "said", "can", "you", "not", "but", "his", "her", "its",
         "our", "one", "all", "any", "may", "mean", "means", "meant", "sense", "is"}


def _txt(html):
    t = re.sub(r"<[^>]+>", " ", html or "")
    t = t.replace("&mdash;", "--").replace("&ldquo;", '"').replace("&rdquo;", '"')
    t = t.replace("&rsquo;", "'").replace("&lsquo;", "'").replace("&amp;", "&").replace("&hellip;", "...")
    return re.sub(r"\s+", " ", t).strip()


def build():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if os.path.exists(DB):
        os.remove(DB)
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE qa(id INTEGER PRIMARY KEY, slug TEXT, question TEXT,"
                " nq TEXT, category TEXT, answer_html TEXT, answer_text TEXT, refs TEXT)")
    con.execute("CREATE INDEX idx_nq ON qa(nq)")
    con.execute("CREATE VIRTUAL TABLE qa_fts USING fts5(question, answer_text, category)")
    seen, n, files = set(), 0, sorted(glob.glob(BATCH_GLOB))
    for f in files:
        try:
            rows = json.load(open(f, encoding="utf-8"))
        except Exception as e:
            print("  BAD JSON:", os.path.basename(f), e)
            continue
        for r in rows:
            q = (r.get("question") or "").strip()
            slug = (r.get("slug") or re.sub(r"[^a-z0-9]+", "-", q.lower())).strip("-")
            key = slug or q.lower()
            if not q or key in seen:
                continue
            seen.add(key)
            ah = r.get("answer_html") or ""
            at = _txt(ah)
            refs = r.get("refs") or []
            cur = con.execute("INSERT INTO qa(slug,question,nq,category,answer_html,answer_text,refs)"
                              " VALUES(?,?,?,?,?,?,?)",
                              (slug, q, _norm(q), r.get("category", ""), ah, at, "; ".join(refs)))
            con.execute("INSERT INTO qa_fts(rowid,question,answer_text,category) VALUES(?,?,?,?)",
                        (cur.lastrowid, q, at, r.get("category", "")))
            n += 1
    con.commit()
    con.close()
    print("KB built: %d entries from %d batch files -> %s" % (n, len(files), DB))
    return n


def _match(query):
    toks = [t for t in re.findall(r"[A-Za-z]{3,}", query.lower()) if t not in _STOP]
    seen, out = set(), []
    for t in toks:
        if t not in seen:
            seen.add(t)
            out.append('"%s"' % t)
    return " OR ".join(out[:12])


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def search(query, limit=3):
    if not os.path.exists(DB):
        return []
    try:
        con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    except Exception:
        return []
    nq = _norm(query)
    out, seen = [], set()
    try:
        # 1) EXACT normalized-question match first -- guarantees faithful recall even
        #    when the exact row would not rank in the FTS top-N.
        ex = con.execute("SELECT question,answer_text,category,refs FROM qa WHERE nq=? LIMIT 1",
                         (nq,)).fetchone()
        if ex:
            out.append({"question": ex[0], "answer": ex[1], "category": ex[2],
                        "refs": ex[3], "exact": True})
            seen.add(ex[0])
        # 2) FTS for related answers
        m = _match(query)
        rows = con.execute(
            "SELECT q.question,q.answer_text,q.category,q.refs,bm25(qa_fts) AS r"
            " FROM qa_fts JOIN qa q ON q.id=qa_fts.rowid WHERE qa_fts MATCH ?"
            " ORDER BY r LIMIT ?", (m, limit + 3)).fetchall() if m else []
    except Exception:
        rows = []
    finally:
        con.close()
    for question, at, cat, refs, r in rows:
        if question in seen:
            continue
        seen.add(question)
        out.append({"question": question, "answer": at, "category": cat,
                    "refs": refs, "exact": _norm(question) == nq})
        if len(out) >= limit:
            break
    return out[:limit]


def grounding_block(query, limit=2):
    """Authoritative installed-answer grounding. An exact/near question match is
    flagged so Tav'iel reproduces the settled answer faithfully (recall)."""
    hits = search(query, limit=limit)
    if not hits:
        return "", []
    lines, srcs = [], []
    top = hits[0]
    if top["exact"]:
        lines.append("TAV'IEL SETTLED ANSWER (this exact question has an installed "
                     "answer -- give THIS answer faithfully, in your own voice):")
        lines.append("- " + top["answer"])
        srcs.append("kb:%s" % top["question"][:40])
        hits = hits[1:]
    if hits:
        lines.append("RELATED INSTALLED ANSWERS (align with these):")
        for h in hits:
            lines.append("- Q: %s | %s" % (h["question"], h["answer"][:400]))
            srcs.append("kb:%s" % h["question"][:40])
    return "\n".join(lines), srcs


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        build()
    else:
        q = sys.argv[1] if len(sys.argv) > 1 else "What is the church?"
        for h in search(q):
            print("[exact=%s] %s" % (h["exact"], h["question"]))
            print("   ", h["answer"][:200])
