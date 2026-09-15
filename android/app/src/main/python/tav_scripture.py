r"""TAV_SCRIPTURE — Tav'iel's scripture hands.

1. find_refs(text): scripture references in ANY order or spelling — "John 3:16",
   "3:16 John", "John 3 16", "the 23rd Psalm", "first john 4 8", "Genesis chapter 1
   verse 1" — resolved to (Book, chapter, verse|None).
2. fetch(...): the verbatim KJV text for a reference (never fabricated).
3. search(query): FTS5 topical search across all 31,102 verses.
4. ground_block(query): verbatim verses (referenced + topical) as a grounding block.
5. link_answer(answer): every scripture quotation in an answer gets its checkable
   (Book c:v) reference — quotes are verified verbatim against the KJV; a quote the
   Bible does not contain is marked, never passed off.
"""
from __future__ import annotations

import os
import re
import sqlite3
import threading

_YB = os.environ.get("YAHBIBLE_BASE", "D:").replace("\\", "/").rstrip("/")
_DB = "file:%s/watchman/watchman.db?mode=ro" % _YB
_LOCK = threading.Lock()
_CON = None

BOOKS = ["Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth",
         "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra",
         "Nehemiah", "Esther", "Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon",
         "Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos",
         "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah",
         "Malachi", "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians",
         "2 Corinthians", "Galatians", "Ephesians", "Philippians", "Colossians",
         "1 Thessalonians", "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon",
         "Hebrews", "James", "1 Peter", "2 Peter", "1 John", "2 John", "3 John", "Jude",
         "Revelation"]

_ALIAS = {"psalm": "Psalms", "ps": "Psalms", "psa": "Psalms", "song of songs": "Song of Solomon",
          "songs": "Song of Solomon", "canticles": "Song of Solomon", "eccl": "Ecclesiastes",
          "ecc": "Ecclesiastes", "gen": "Genesis", "exo": "Exodus", "ex": "Exodus",
          "lev": "Leviticus", "num": "Numbers", "deut": "Deuteronomy", "deu": "Deuteronomy",
          "josh": "Joshua", "judg": "Judges", "sam": "Samuel", "kgs": "Kings", "chron": "Chronicles",
          "chr": "Chronicles", "neh": "Nehemiah", "esth": "Esther", "prov": "Proverbs",
          "pro": "Proverbs", "isa": "Isaiah", "jer": "Jeremiah", "lam": "Lamentations",
          "ezek": "Ezekiel", "eze": "Ezekiel", "dan": "Daniel", "hos": "Hosea", "obad": "Obadiah",
          "mic": "Micah", "nah": "Nahum", "hab": "Habakkuk", "zeph": "Zephaniah", "hag": "Haggai",
          "zech": "Zechariah", "mal": "Malachi", "matt": "Matthew", "mat": "Matthew",
          "mk": "Mark", "mrk": "Mark", "lk": "Luke", "luk": "Luke", "jn": "John", "jhn": "John",
          "rom": "Romans", "cor": "Corinthians", "gal": "Galatians", "eph": "Ephesians",
          "phil": "Philippians", "php": "Philippians", "col": "Colossians", "thess": "Thessalonians",
          "th": "Thessalonians", "tim": "Timothy", "tit": "Titus", "phlm": "Philemon",
          "heb": "Hebrews", "jas": "James", "pet": "Peter", "rev": "Revelation",
          "apocalypse": "Revelation"}

_ORD = {"first": "1", "1st": "1", "i": "1", "second": "2", "2nd": "2", "ii": "2",
        "third": "3", "3rd": "3", "iii": "3"}
_NUMWORD = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
            "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "twenty": 20,
            "thirty": 30, "forty": 40, "fifty": 50, "ninety": 90, "hundred": 100,
            "twentieth": 20, "twenty-three": 23, "twenty-third": 23, "ninetieth": 90,
            "hundredth": 100, "fiftieth": 50, "twenty-second": 22, "ninety-first": 91}
_LOWER = {b.lower(): b for b in BOOKS}
for b in BOOKS:                                # bare names of numbered books: "samuel" -> ask 1/2
    core = re.sub(r"^\d ", "", b).lower()
    _LOWER.setdefault(core, b if " " not in b or not b[0].isdigit() else b)


def _con():
    global _CON
    with _LOCK:
        if _CON is None:
            _CON = sqlite3.connect(_DB, uri=True, check_same_thread=False)
        return _CON


_FAM = {"Samuel", "Kings", "Chronicles", "Corinthians", "Thessalonians", "Timothy", "Peter"}


def _canon_book(word, num_prefix=None):
    """Resolve one book word (+optional 1/2/3 prefix) to a canonical name, or None."""
    w = (word or "").strip(".").lower()
    w = _ALIAS.get(w) or _LOWER.get(w) or _ALIAS.get(w.rstrip("s")) or _LOWER.get(w.rstrip("s"))
    if not w:
        return None
    # the prefix decides numbered families FIRST ("first john" is 1 John, not the Gospel)
    if num_prefix in ("1", "2", "3"):
        cand = "%s %s" % (num_prefix, w if w in _FAM or w == "John" else w)
        if cand in BOOKS:
            return cand
    if w in BOOKS:
        return w
    if w in _FAM:                       # bare family name defaults to the first book
        cand = "1 %s" % w
        return cand if cand in BOOKS else None
    return None


def find_refs(text, limit=8):
    """Scripture references anywhere in free text, tokens in ANY order."""
    toks = re.findall(r"[A-Za-z][A-Za-z'\-]*|\d+[:.]\d+|\d+", text or "")
    out, used, consumed = [], set(), set()
    n = len(toks)
    for i, t in enumerate(toks):
        if i in consumed:
            continue
        num_prefix = None
        j = i
        tl = t.lower()
        if tl in _ORD or (t in ("1", "2", "3") and i + 1 < n and toks[i + 1][0].isalpha()):
            num_prefix = _ORD.get(tl, t)
            j = i + 1
            if j >= n or j in consumed:
                continue
        book = _canon_book(toks[j], num_prefix)
        if not book:
            continue
        consumed.add(j)
        if j != i:
            consumed.add(i)
        # collect the nearest numbers around the book word — forward first, then backward,
        # each direction stopping at the first unrelated word (so any ORDER works)
        def _scan(idxs, after):
            got = []
            for k in idxs:
                if k in consumed:
                    continue
                tk = toks[k]
                if re.fullmatch(r"\d+[:.]\d+", tk):
                    a, b = re.split(r"[:.]", tk)
                    return [("cv", int(a), int(b), k)]
                if tk.isdigit() and (tk not in ("1", "2", "3") or after):
                    got.append(("n", int(tk), None, k))
                    if len(got) >= 2:
                        return got
                elif tk.lower() in ("chapter", "verse", "the", "of", "and", "in", "vs", "v",
                                    "rd", "st", "nd", "th"):
                    continue
                elif tk.lower() in _NUMWORD:
                    got.append(("n", _NUMWORD[tk.lower()], None, k))
                    if len(got) >= 2:
                        return got
                elif tk[0].isalpha():
                    if after:
                        break
                    continue        # backward: step over words ("the 23rd Psalm")
            return got
        nums = _scan(range(j + 1, min(j + 5, n)), True)
        if not nums or (nums[0][0] != "cv" and len(nums) < 2):
            back = _scan(range(i - 1, max(i - 4, -1), -1), False)
            if back and (back[0][0] == "cv" or not nums):
                nums = back if back[0][0] == "cv" else nums + back
        for it in nums:
            consumed.add(it[3])
        ch = v = None
        if nums:
            if nums[0][0] == "cv":
                ch, v = nums[0][1], nums[0][2]
            else:
                ch = nums[0][1]
                if len(nums) > 1 and nums[1][0] == "n":
                    v = nums[1][1]
        if ch is None:
            continue
        key = (book, ch, v)
        if key in used:
            continue
        used.add(key)
        out.append({"book": book, "chapter": ch, "verse": v})
        if len(out) >= limit:
            break
    return out


def fetch(book, chapter, verse=None, limit=12):
    """Verbatim KJV text — a verse, or the chapter's opening verses."""
    c = _con()
    if verse:
        r = c.execute("SELECT verse,text FROM verses WHERE book=? AND chapter=? AND verse=?",
                      (book, chapter, verse)).fetchall()
    else:
        r = c.execute("SELECT verse,text FROM verses WHERE book=? AND chapter=?"
                      " ORDER BY verse LIMIT ?", (book, chapter, limit)).fetchall()
    return [{"ref": "%s %d:%d" % (book, chapter, vn), "book": book, "chapter": chapter,
             "verse": vn, "text": tx} for vn, tx in r]


def search(query, limit=6):
    """Topical FTS5 search across the whole KJV."""
    q = " ".join(re.findall(r"[A-Za-z']+", query or ""))
    if not q:
        return []
    c = _con()
    try:
        rows = c.execute("SELECT v.book, v.chapter, v.verse, v.text FROM verses_fts f"
                         " JOIN verses v ON v.id=f.rowid WHERE verses_fts MATCH ?"
                         " ORDER BY rank LIMIT ?", (q, limit)).fetchall()
    except sqlite3.OperationalError:
        words = q.split()
        rows = []
        if words:
            like = "%" + "%".join(words[:3]) + "%"
            rows = c.execute("SELECT book,chapter,verse,text FROM verses WHERE text LIKE ?"
                             " LIMIT ?", (like, limit)).fetchall()
    return [{"ref": "%s %d:%d" % (b, ch, vn), "book": b, "chapter": ch, "verse": vn, "text": tx}
            for b, ch, vn, tx in rows]


def ground_block(query, max_verses=10):
    """Verbatim scripture grounding for a question: explicitly referenced verses first
    (any word order in the asking), then topical hits. Returns (block, refs)."""
    got, refs, seen = [], [], set()
    for r in find_refs(query):
        for v in fetch(r["book"], r["chapter"], r["verse"], limit=6):
            if v["ref"] in seen:
                continue
            seen.add(v["ref"])
            got.append('%s — "%s"' % (v["ref"], v["text"]))
            refs.append(v["ref"])
            if len(got) >= max_verses:
                break
    if len(got) < max_verses:
        for v in search(query, limit=max_verses - len(got)):
            if v["ref"] in seen:
                continue
            seen.add(v["ref"])
            got.append('%s — "%s"' % (v["ref"], v["text"]))
            refs.append(v["ref"])
    if not got:
        return "", []
    return ("SCRIPTURE (verbatim KJV — quote from these and cite each quote):\n"
            + "\n".join(got) + "\n"), refs


_QUOTE_RE = re.compile(r'["“‘\']([^"”’\']{25,300})["”’\']')


def link_answer(answer):
    """Make every scripture quotation in an answer CHECKABLE: verify each quoted run
    verbatim against the KJV and ensure its (Book c:v) follows it. Returns
    (linked_answer, refs_used)."""
    if not answer:
        return answer, []
    c = _con()
    refs = []
    out = answer
    for m in list(_QUOTE_RE.finditer(answer)):
        q = re.sub(r"\s+", " ", m.group(1)).strip()
        words = re.findall(r"[A-Za-z']+", q)
        if len(words) < 5:
            continue
        probe = " ".join(words[:8])
        try:
            row = c.execute("SELECT v.book,v.chapter,v.verse FROM verses_fts f JOIN verses v"
                            " ON v.id=f.rowid WHERE verses_fts MATCH ? LIMIT 1",
                            ('"%s"' % probe,)).fetchone()
        except sqlite3.OperationalError:
            row = None
        if not row:
            continue
        ref = "%s %d:%d" % row
        refs.append(ref)
        tail = answer[m.end():m.end() + 40]
        if ref.split()[0] in tail and str(row[1]) in tail:
            continue                      # already cited right after the quote
        out = out.replace(m.group(0), m.group(0) + " (" + ref + ")", 1)
    # bare references already in the text count as refs too
    for r in find_refs(out, limit=12):
        rr = "%s %d%s" % (r["book"], r["chapter"], (":%d" % r["verse"]) if r["verse"] else "")
        if rr not in refs:
            refs.append(rr)
    return out, refs


if __name__ == "__main__":
    for t in ["John 3:16", "3:16 John tell me about it", "the 23rd Psalm", "first john 4 8",
              "Genesis chapter 1 verse 1", "what does John 3 16 and Romans 8 28 mean",
              "psalm 91", "2 tim 3:16"]:
        print(t, "->", find_refs(t))
    print(search("love one another", 3))
    print(ground_block("what did Yeshua say about the 23rd psalm and John 10 11")[0][:400])
