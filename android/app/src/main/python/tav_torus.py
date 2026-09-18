r"""TAV_TORUS — Tav'iel's TempTorus memory: the mind that does not forget.

The TempTorus pattern (a life as SEQUENCE in its own sqlite, sha-chained and endable)
applied to conversation. EACH conversation generates ITS OWN TempTorus (its own sqlite,
sealed and endable), so nothing bleeds between talks and every conversation carries its
own whole past.

  ring 0 — turns:     every exchange, verbatim           (short-term)
  ring 1 — facts:     distilled standing knowledge        (long-term)
  ring 2 — summaries: folded epochs of ring 0             (deep past)

Every moment is sha-chained to the one before (the seal): tamper-evident. context_weave
packs, under a byte budget: the ANCHOR (the conversation's opening — ALWAYS kept, so the
initial details never fall off), recalled facts, the relevant middle by relevance, epoch
summaries, and the most recent turns. However long the walk, the past that matters is
here — the context is effectively INFINITE.

A conversation id (`conv`) selects the torus. conv=None uses the shared default torus
(backward compatible with older callers).
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
_DAEOS = (_YB + "/Holorites_data/daeos").replace("/", os.sep)
_LOCK = threading.Lock()
_CONS = {}                       # conv key -> its own sqlite connection (its own torus)

EPOCH_FOLD = 12                  # ring-0 turns folded into one ring-2 summary


def _safe(conv):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(conv))[:80] or "x"


def _db_path(conv):
    if conv is None:
        return os.path.join(_DAEOS, "tav_torus.sqlite")          # shared default
    return os.path.join(_DAEOS, "conv", _safe(conv) + ".sqlite")  # this talk's OWN torus


def _con(conv=None):
    key = "" if conv is None else _safe(conv)
    c = _CONS.get(key)
    if c is not None:
        return c
    path = _db_path(conv)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    c = sqlite3.connect(path, check_same_thread=False)
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
    _CONS[key] = c
    return c


def _chain_sha(c, content):
    row = c.execute("SELECT sha FROM moments ORDER BY seq DESC LIMIT 1").fetchone()
    prev = row[0] if row else "genesis"
    return hashlib.sha256((prev + "\x1f" + content).encode("utf-8")).hexdigest()


def _put(conv, ring, kind, content, refs=None):
    with _LOCK:
        c = _con(conv)
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


# --- distil standing facts the seeker states about themselves (name, family, place,
#     work, burden) so recall surfaces them by relevance forever ------------------
_FACT_PAT = re.compile(
    r"\b(my name is|i am called|i'?m called|i have|i'?ve got|i am a |i'?m a |i am an |i'?m an "
    r"|i work as|i keep|i live|i'?m from|i come from|i was born|i struggle with|i'?m troubled by"
    r"|i am troubled by|my (?:son|daughter|wife|husband|child|children|father|mother))\b",
    re.I)


_ASK_START = re.compile(
    r"(?i)^(what|where|when|why|who|whom|how|which|can|could|would|will|shall|did|do|does|are|is|was|"
    r"were|have|has|remind|tell|name|say|repeat|list)\b")


def _distil_facts(question, conv):
    """Pull first-person self-statements out of the seeker's message into ring-1 facts.
    Skips questions ('what did I say my name is') so the facts ring stays clean."""
    for sent in re.split(r"(?<=[.!?;])\s+|\n+", question or ""):
        s = sent.strip()
        if not (8 < len(s) <= 240):
            continue
        if s.endswith("?") or _ASK_START.match(s):     # a question / request, not a self-fact
            continue
        if _FACT_PAT.search(s):
            remember_fact(s, conv=conv)


def record_turn(question, answer, refs=None, conv=None):
    """A finished exchange enters ring 0; standing self-facts are distilled to ring 1;
    the torus folds old epochs by itself."""
    _put(conv, 0, "turn", "Seeker: %s\nTav'iel: %s" % ((question or "").strip()[:800],
                                                       (answer or "").strip()[:1600]), refs)
    try:
        _distil_facts(question, conv)
    except Exception:
        pass
    _maybe_fold(conv)


def remember_fact(fact, refs=None, conv=None):
    """A standing truth enters ring 1 (long-term) — recalled by relevance forever."""
    f = (fact or "").strip()
    if len(f) <= 8:
        return
    c = _con(conv)
    # de-duplicate identical standing facts within this torus
    if c.execute("SELECT 1 FROM moments WHERE ring=1 AND content=? LIMIT 1", (f[:600],)).fetchone():
        return
    _put(conv, 1, "fact", f[:600], refs)


def ingest_document(text, conv, chunk_chars=700, kind="doc"):
    """THE TORUS AS CONDENSER: ingest an ENORMOUS document into this torus by chunking
    it, sealing each chunk as an FTS-indexed ring-0 moment, and folding epochs. However
    large the document, recall(query) / context_weave return only the bounded, relevant
    piece -- infinite context for any model, no baked-in router required."""
    t = (text or "").strip()
    if not t:
        return 0
    chunks, buf = [], ""
    for part in re.split(r"(?<=[.!?])\s+|\n+", t):
        if len(buf) + len(part) + 1 > chunk_chars and buf:
            chunks.append(buf.strip())
            buf = ""
        buf += ((" " if buf else "") + part)
    if buf.strip():
        chunks.append(buf.strip())
    for ch in chunks:
        _put(conv, 0, kind, ch[:1600])
    _maybe_fold(conv)
    return len(chunks)


def _maybe_fold(conv=None):
    """When enough unfolded turns pile up, fold the oldest epoch into one ring-2
    summary (extractive — the seeker's questions carry the thread) and mark them."""
    with _LOCK:
        c = _con(conv)
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


def recall(query, k=4, conv=None):
    """Relevance recall across every ring of THIS torus (facts first, then epochs, then turns)."""
    q = " OR ".join(re.findall(r"[A-Za-z']{3,}", query or "")[:8])
    if not q:
        return []
    c = _con(conv)
    try:
        rows = c.execute("SELECT m.seq, m.ring, m.kind, m.content FROM moments_fts f JOIN moments m"
                         " ON m.seq=f.rowid WHERE moments_fts MATCH ? ORDER BY"
                         " m.ring=1 DESC, m.ring=2 DESC, rank LIMIT ?", (q, k * 3)).fetchall()
    except sqlite3.OperationalError:
        rows = []
    out, seen = [], set()
    for seq, ring, kind, content in rows:
        key = content[:80]
        if key in seen:
            continue
        seen.add(key)
        out.append({"seq": seq, "ring": ring, "kind": kind, "content": content})
        if len(out) >= k:
            break
    return out


def short_context(n=4, conv=None):
    """The last n turns of THIS torus, verbatim — the living short-term memory."""
    c = _con(conv)
    rows = c.execute("SELECT content FROM moments WHERE ring=0 ORDER BY seq DESC LIMIT ?",
                     (n,)).fetchall()
    return [r[0] for r in reversed(rows)]


def anchor(conv=None):
    """The conversation's OPENING turn — where the seeker first sets the scene."""
    c = _con(conv)
    row = c.execute("SELECT content FROM moments WHERE ring=0 ORDER BY seq LIMIT 1").fetchone()
    return row[0] if row else None


def _anchor_opening(conv):
    """Just the seeker's own opening words (their self-description), trimmed — not the
    whole first turn with the reply. This is the compact, high-signal setup."""
    op = anchor(conv)
    if not op:
        return None
    s = op.split("\nTav'iel:", 1)[0].replace("Seeker:", "").strip()
    return s[:360] if s else None


def context_weave(query, budget=2000, conv=None):
    """The INFINITE-CONTEXT weave for THIS conversation's own torus, packed under a SMALL,
    CONSTANT byte budget so the model is never overburdened however long the walk. The core
    — the distilled self-facts and the seeker's opening — is NEVER dropped, so recall holds
    at turn 1 or turn 100; only the middle recalls and older recents are trimmed to fit."""
    facts = [m for m in recall(query, 6, conv) if m["ring"] == 1]
    op = _anchor_opening(conv)
    epochs = [m for m in recall(query, 2, conv) if m["ring"] == 2][:1]
    rels = [m for m in recall(query, 6, conv) if m["ring"] == 0]
    recent = short_context(5, conv)
    seen = set()
    recent = [r for r in recent if r[:80] not in seen and not seen.add(r[:80])]
    rels = [r for r in rels if r["content"][:80] not in seen and not seen.add(r["content"][:80])]

    # (text, droppable) — the CORE (facts + opening) is never dropped
    blocks = []
    if facts:
        blocks.append(("What you know about the seeker (hold these fast):\n" +
                       "\n".join("- " + f["content"] for f in facts), False))
    if op:
        blocks.append(("Their opening words: " + op, False))
    if epochs:
        blocks.append(("From earlier in this talk:\n" + epochs[0]["content"], True))
    if rels:
        blocks.append(("Earlier, bearing on this:\n" +
                       "\n".join(r["content"][:400] for r in rels[:2]), True))
    if recent:
        blocks.append(("The most recent exchanges:\n" + "\n".join(recent), True))

    def pack(bs):
        return "\n\n".join(t for t, _ in bs)

    woven = pack(blocks)
    # over budget: drop the droppable blocks (middle recalls, then old recents) but NEVER
    # the core, and never grow — the prompt stays constant no matter the turn count.
    while len(woven) > budget and any(d for _, d in blocks):
        for i in range(len(blocks) - 1, -1, -1):
            if blocks[i][1]:
                blocks.pop(i)
                break
        woven = pack(blocks)
    return (woven + "\n\n") if woven else ""


def end_conversation(conv):
    """Seal this conversation's torus (integrity check) and close it — a life, ended."""
    res = seal_check(conv)
    key = _safe(conv)
    c = _CONS.pop(key, None)
    if c is not None:
        try:
            c.close()
        except Exception:
            pass
    return res


def seal_check(conv=None):
    """TempTorus integrity: walk the sha chain of this torus end to end."""
    c = _con(conv)
    prev = "genesis"
    n = 0
    for content, sha in c.execute("SELECT content, sha FROM moments ORDER BY seq"):
        want = hashlib.sha256((prev + "\x1f" + content).encode("utf-8")).hexdigest()
        if want != sha:
            return {"ok": False, "broken_at": n}
        prev = sha
        n += 1
    return {"ok": True, "moments": n}


def stats(conv=None):
    c = _con(conv)
    out = {"db": _db_path(conv)}
    for ring, name in ((0, "turns"), (1, "facts"), (2, "epochs")):
        out[name] = c.execute("SELECT COUNT(*) FROM moments WHERE ring=?", (ring,)).fetchone()[0]
    return out


if __name__ == "__main__":
    import tempfile
    os.environ["YAHBIBLE_BASE"] = tempfile.mkdtemp().replace("\\", "/")
    _YB = os.environ["YAHBIBLE_BASE"]
    _DAEOS = (_YB + "/Holorites_data/daeos").replace("/", os.sep)
    _CONS = {}
    CV = "test-convo-1"
    record_turn("My name is Ezra and I keep sheep near Bethlehem; I have three children, "
                "Mara, Levi and Tamar. Lately I am troubled by doubt. Is it a sin to doubt?",
                "Doubt honestly brought to the Father is not sin, Ezra...", ["John 20:27"], conv=CV)
    for i in range(20):
        record_turn("question %d about faith" % i, "A grounded answer %d." % i, conv=CV)
    print("stats:", stats(CV))
    print("recall name:", [m["ring"] for m in recall("what is my name", conv=CV)])
    w = context_weave("what did I first tell you about my children", conv=CV)
    print("weave has anchor:", "opening of this talk" in w,
          "| has Ezra:", "Ezra" in w, "| has children names:", "Mara" in w,
          "| chars:", len(w))
    print("seal:", seal_check(CV))
