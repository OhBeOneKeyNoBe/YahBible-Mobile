r"""TAV_TORUS — Tav'iel's TempTorus memory: the mind that does not forget.

The TempTorus pattern (a life as SEQUENCE in its own sqlite, sha-chained and endable)
applied to conversation: every moment lives on a ring, and the WEAVE brings back what
matters so the context is effectively INFINITE — nothing falls off the world; it lives
in the torus and returns by relevance.

  ring 0 — turns:     every exchange, verbatim           (short-term)
  ring 1 — facts:     distilled standing knowledge       (long-term)
  ring 2 — summaries: folded epochs of ring 0            (deep past)

Each moment is sha-chained to the one before (the TempTorus seal): the memory's
history is tamper-evident. context_weave(query, budget) packs recent turns + recalled
facts + epoch summaries under a byte budget — the model always reasons with a woven
past regardless of how long the walk has been.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import time

_YB = os.environ.get("YAHBIBLE_BASE", "D:").replace("\\", "/").rstrip("/")
DB = (_YB + "/Holorites_data/daeos/tav_torus.sqlite").replace("/", os.sep)
_LOCK = threading.Lock()
_CON = None

EPOCH_FOLD = 12          # ring-0 turns folded into one ring-2 summary


def _con():
    global _CON
    if _CON is None:
        os.makedirs(os.path.dirname(DB), exist_ok=True)
        c = sqlite3.connect(DB, check_same_thread=False)
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("""CREATE TABLE IF NOT EXISTS moments(
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL, ring INTEGER NOT NULL, kind TEXT NOT NULL,
            content TEXT NOT NULL, refs TEXT, folded INTEGER DEFAULT 0, sha TEXT NOT NULL)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_m_ring ON moments(ring, folded)")
        try:
            c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS moments_fts USING fts5("
                      "content, content_rowid='seq', content='moments')")
        except sqlite3.OperationalError:
            pass
        c.commit()
        _CON = c
    return _CON


def _chain_sha(c, content):
    row = c.execute("SELECT sha FROM moments ORDER BY seq DESC LIMIT 1").fetchone()
    prev = row[0] if row else "genesis"
    return hashlib.sha256((prev + "\x1f" + content).encode("utf-8")).hexdigest()


def _put(ring, kind, content, refs=None):
    with _LOCK:
        c = _con()
        sha = _chain_sha(c, content)
        cur = c.execute("INSERT INTO moments(ts,ring,kind,content,refs,sha) VALUES(?,?,?,?,?,?)",
                        (time.time(), ring, kind, content, json.dumps(refs or []), sha))
        try:
            c.execute("INSERT INTO moments_fts(rowid, content) VALUES(?,?)",
                      (cur.lastrowid, content))
        except sqlite3.OperationalError:
            pass
        c.commit()
        return cur.lastrowid


def record_turn(question, answer, refs=None):
    """A finished exchange enters ring 0; the torus folds old epochs by itself."""
    _put(0, "turn", "Seeker: %s\nTav'iel: %s" % ((question or "").strip()[:800],
                                                 (answer or "").strip()[:1600]), refs)
    _maybe_fold()


def remember_fact(fact, refs=None):
    """A standing truth enters ring 1 (long-term) — recalled by relevance forever."""
    if fact and len(fact.strip()) > 8:
        _put(1, "fact", fact.strip()[:600], refs)


def _maybe_fold():
    """When enough unfolded turns pile up, fold the oldest epoch into one ring-2
    summary (extractive — the seeker's questions carry the thread) and mark them."""
    with _LOCK:
        c = _con()
        rows = c.execute("SELECT seq, content FROM moments WHERE ring=0 AND folded=0"
                         " ORDER BY seq LIMIT ?", (EPOCH_FOLD * 2,)).fetchall()
        if len(rows) < EPOCH_FOLD * 2:
            return
        fold = rows[:EPOCH_FOLD]
        lines = []
        for _, content in fold:
            q = content.split("\n", 1)[0].replace("Seeker: ", "").strip()
            a = content.split("Tav'iel: ", 1)[-1].strip()
            first = re.split(r"(?<=[.!?])\s", a, 1)[0][:160]
            lines.append("asked %s — held: %s" % (q[:110], first))
        summary = "Epoch of %d exchanges:\n" % len(fold) + "\n".join(lines)
        sha = _chain_sha(c, summary)
        cur = c.execute("INSERT INTO moments(ts,ring,kind,content,refs,sha) VALUES(?,?,?,?,?,?)",
                        (time.time(), 2, "epoch", summary, "[]", sha))
        try:
            c.execute("INSERT INTO moments_fts(rowid, content) VALUES(?,?)", (cur.lastrowid, summary))
        except sqlite3.OperationalError:
            pass
        c.execute("UPDATE moments SET folded=1 WHERE seq IN (%s)"
                  % ",".join(str(s) for s, _ in fold))
        c.commit()


def recall(query, k=4):
    """Relevance recall across every ring (facts first, then epochs, then old turns)."""
    q = " OR ".join(re.findall(r"[A-Za-z']{3,}", query or "")[:8])
    if not q:
        return []
    c = _con()
    try:
        rows = c.execute("SELECT m.ring, m.kind, m.content FROM moments_fts f JOIN moments m"
                         " ON m.seq=f.rowid WHERE moments_fts MATCH ? ORDER BY"
                         " m.ring=1 DESC, m.ring=2 DESC, rank LIMIT ?", (q, k * 2)).fetchall()
    except sqlite3.OperationalError:
        rows = []
    out, seen = [], set()
    for ring, kind, content in rows:
        key = content[:80]
        if key in seen:
            continue
        seen.add(key)
        out.append({"ring": ring, "kind": kind, "content": content})
        if len(out) >= k:
            break
    return out


def short_context(n=4):
    """The last n turns, verbatim — the living short-term memory."""
    c = _con()
    rows = c.execute("SELECT content FROM moments WHERE ring=0 ORDER BY seq DESC LIMIT ?",
                     (n,)).fetchall()
    return [r[0] for r in reversed(rows)]


def context_weave(query, budget=2400):
    """The INFINITE-CONTEXT weave: recent turns + recalled facts + epoch summaries,
    packed under a byte budget. However long the walk, the past that matters is here."""
    parts = []
    facts = [m for m in recall(query, 4) if m["ring"] == 1]
    if facts:
        parts.append("Standing knowledge (from earlier walks):\n" +
                      "\n".join("- " + f["content"] for f in facts))
    epochs = [m for m in recall(query, 3) if m["ring"] == 2][:1]
    if epochs:
        parts.append("From the deep past:\n" + epochs[0]["content"])
    recent = short_context(4)
    if recent:
        parts.append("Conversation so far:\n" + "\n".join(recent))
    woven = "\n\n".join(parts)
    while len(woven) > budget and parts:
        parts.pop(0)
        woven = "\n\n".join(parts)
    return (woven + "\n\n") if woven else ""


def seal_check():
    """TempTorus integrity: walk the sha chain end to end."""
    c = _con()
    prev = "genesis"
    n = 0
    for content, sha in c.execute("SELECT content, sha FROM moments ORDER BY seq"):
        want = hashlib.sha256((prev + "\x1f" + content).encode("utf-8")).hexdigest()
        if want != sha:
            return {"ok": False, "broken_at": n}
        prev = sha
        n += 1
    return {"ok": True, "moments": n}


def stats():
    c = _con()
    out = {"db": DB}
    for ring, name in ((0, "turns"), (1, "facts"), (2, "epochs")):
        out[name] = c.execute("SELECT COUNT(*) FROM moments WHERE ring=?", (ring,)).fetchone()[0]
    return out


if __name__ == "__main__":
    import tempfile
    os.environ["YAHBIBLE_BASE"] = tempfile.mkdtemp().replace("\\", "/")
    _YB = os.environ["YAHBIBLE_BASE"]
    DB = (_YB + "/Holorites_data/daeos/tav_torus.sqlite").replace("/", os.sep)
    _CON = None
    for i in range(30):
        record_turn("question %d about the shepherd psalm" % i,
                    "The LORD is my shepherd; I shall not want. Answer %d." % i, ["Psalms 23:1"])
    remember_fact("The seeker loves Psalm 23 and asks of shepherds often.")
    print("stats:", stats())
    print("recall:", [m["kind"] for m in recall("shepherd psalm")])
    w = context_weave("tell me again of the shepherd")
    print("weave chars:", len(w), "| has facts:", "Standing knowledge" in w,
          "| has epoch:", "deep past" in w, "| has recent:", "Conversation so far" in w)
    print("seal:", seal_check())
