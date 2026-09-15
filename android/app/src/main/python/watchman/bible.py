"""bible.py — Watchman's KJV archive: the complete King James Bible with perfect, verbatim recall.

The whole KJV (66 books, 31,102 verses) is loaded into SQLite with an FTS5 full-text index, so the
app has the entire text in its own archive and can search it verbatim (exact phrase) or by reference.
Semantic (topical) retrieval is layered on top in discern.py; this module is the verbatim ground truth.

Source: a clean public-domain KJV in per-book JSON (data/kjv/*.json). No scraping at runtime -- the
text is vendored and vetted once (prove_bible.py checks the count and spot verses byte-exact).

    build_db()                 -- (re)build watchman.db from data/kjv/*.json
    verse("John", 3, 16)       -- exact verse text, verbatim
    ref("John 3:16")           -- same, by human reference string
    search_verbatim("phrase")  -- FTS5 exact-phrase search across all 31,102 verses
    passage("John",3,16,18)    -- a verse range
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "kjv"
DB = ROOT / "watchman.db"
# Relocatable (phone / portable): YAHBIBLE_BASE points at the data tree that carries
# watchman/watchman.db — the module itself may live inside an APK where ROOT is not real.
import os as _os
_yb = _os.environ.get("YAHBIBLE_BASE")
if _yb and (Path(_yb) / "watchman" / "watchman.db").exists():
    DB = Path(_yb) / "watchman" / "watchman.db"
TOTAL_VERSES = 31_102

# canonical 66-book order + display names (JSON filename -> display book name)
BOOKS = [
    ("Genesis", "Genesis"), ("Exodus", "Exodus"), ("Leviticus", "Leviticus"), ("Numbers", "Numbers"),
    ("Deuteronomy", "Deuteronomy"), ("Joshua", "Joshua"), ("Judges", "Judges"), ("Ruth", "Ruth"),
    ("1Samuel", "1 Samuel"), ("2Samuel", "2 Samuel"), ("1Kings", "1 Kings"), ("2Kings", "2 Kings"),
    ("1Chronicles", "1 Chronicles"), ("2Chronicles", "2 Chronicles"), ("Ezra", "Ezra"),
    ("Nehemiah", "Nehemiah"), ("Esther", "Esther"), ("Job", "Job"), ("Psalms", "Psalms"),
    ("Proverbs", "Proverbs"), ("Ecclesiastes", "Ecclesiastes"), ("SongofSolomon", "Song of Solomon"),
    ("Isaiah", "Isaiah"), ("Jeremiah", "Jeremiah"), ("Lamentations", "Lamentations"),
    ("Ezekiel", "Ezekiel"), ("Daniel", "Daniel"), ("Hosea", "Hosea"), ("Joel", "Joel"), ("Amos", "Amos"),
    ("Obadiah", "Obadiah"), ("Jonah", "Jonah"), ("Micah", "Micah"), ("Nahum", "Nahum"),
    ("Habakkuk", "Habakkuk"), ("Zephaniah", "Zephaniah"), ("Haggai", "Haggai"), ("Zechariah", "Zechariah"),
    ("Malachi", "Malachi"), ("Matthew", "Matthew"), ("Mark", "Mark"), ("Luke", "Luke"), ("John", "John"),
    ("Acts", "Acts"), ("Romans", "Romans"), ("1Corinthians", "1 Corinthians"),
    ("2Corinthians", "2 Corinthians"), ("Galatians", "Galatians"), ("Ephesians", "Ephesians"),
    ("Philippians", "Philippians"), ("Colossians", "Colossians"), ("1Thessalonians", "1 Thessalonians"),
    ("2Thessalonians", "2 Thessalonians"), ("1Timothy", "1 Timothy"), ("2Timothy", "2 Timothy"),
    ("Titus", "Titus"), ("Philemon", "Philemon"), ("Hebrews", "Hebrews"), ("James", "James"),
    ("1Peter", "1 Peter"), ("2Peter", "2 Peter"), ("1John", "1 John"), ("2John", "2 John"),
    ("3John", "3 John"), ("Jude", "Jude"), ("Revelation", "Revelation"),
]
DISPLAY = {fname: disp for fname, disp in BOOKS}
# accept "John", "john", "1 John", "1john", "Song of Solomon", "songofsolomon" -> display name
_NORM = {}
for _f, _d in BOOKS:
    for key in {_f.lower(), _d.lower(), _d.lower().replace(" ", "")}:
        _NORM[key] = _d


def _iter_verses():
    """Yield (book_order, book_display, chapter, verse, text) verbatim from the vendored JSON."""
    for order, (fname, disp) in enumerate(BOOKS, start=1):
        data = json.loads((DATA / f"{fname}.json").read_text(encoding="utf-8"))
        for ch in data["chapters"]:
            c = int(ch["chapter"])
            for v in ch["verses"]:
                yield order, disp, c, int(v["verse"]), v["text"]


def build_db(db_path: Path | str = DB) -> int:
    """(Re)build the SQLite archive with an FTS5 verbatim index. Returns the verse count."""
    p = Path(db_path)
    if p.exists():
        p.unlink()
    con = sqlite3.connect(p)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(
        """
        CREATE TABLE verses(
            id INTEGER PRIMARY KEY,
            book_order INTEGER NOT NULL,
            book TEXT NOT NULL,
            chapter INTEGER NOT NULL,
            verse INTEGER NOT NULL,
            ref TEXT NOT NULL,
            text TEXT NOT NULL
        );
        CREATE UNIQUE INDEX idx_bcv ON verses(book, chapter, verse);
        CREATE VIRTUAL TABLE verses_fts USING fts5(text, content='verses', content_rowid='id');
        """
    )
    n = 0
    for order, disp, c, v, text in _iter_verses():
        n += 1
        ref = f"{disp} {c}:{v}"
        con.execute(
            "INSERT INTO verses(id, book_order, book, chapter, verse, ref, text) "
            "VALUES(?,?,?,?,?,?,?)", (n, order, disp, c, v, ref, text))
    con.execute("INSERT INTO verses_fts(rowid, text) SELECT id, text FROM verses")
    con.commit()
    con.close()
    return n


def _con(db_path: Path | str = DB) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def _book_name(book: str) -> str:
    key = book.strip().lower()
    if key in _NORM:
        return _NORM[key]
    key2 = key.replace(" ", "")
    if key2 in _NORM:
        return _NORM[key2]
    raise KeyError(f"unknown book {book!r}")


def verse(book: str, chapter: int, v: int, db_path: Path | str = DB) -> str:
    con = _con(db_path)
    row = con.execute("SELECT text FROM verses WHERE book=? AND chapter=? AND verse=?",
                      (_book_name(book), int(chapter), int(v))).fetchone()
    con.close()
    if row is None:
        raise KeyError(f"{book} {chapter}:{v} not found")
    return row["text"]


_REF_RE = re.compile(r"^\s*(.+?)\s+(\d+):(\d+)(?:\s*-\s*(\d+))?\s*$")


def ref(reference: str, db_path: Path | str = DB):
    """'John 3:16' -> text; 'John 3:16-18' -> list of (ref, text)."""
    m = _REF_RE.match(reference)
    if not m:
        raise ValueError(f"bad reference {reference!r}")
    book, c, v1, v2 = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
    if v2 is None:
        return verse(book, c, v1, db_path)
    return passage(book, c, v1, int(v2), db_path)


def passage(book: str, chapter: int, v1: int, v2: int, db_path: Path | str = DB):
    con = _con(db_path)
    rows = con.execute(
        "SELECT ref, text FROM verses WHERE book=? AND chapter=? AND verse BETWEEN ? AND ? "
        "ORDER BY verse", (_book_name(book), int(chapter), int(v1), int(v2))).fetchall()
    con.close()
    return [(r["ref"], r["text"]) for r in rows]


def search_verbatim(phrase: str, limit: int = 25, db_path: Path | str = DB):
    """FTS5 exact-phrase search across all 31,102 verses. Returns [(ref, text), ...]."""
    q = '"' + phrase.replace('"', '""') + '"'
    con = _con(db_path)
    rows = con.execute(
        "SELECT v.ref, v.text FROM verses_fts f JOIN verses v ON v.id=f.rowid "
        "WHERE verses_fts MATCH ? ORDER BY v.book_order, v.chapter, v.verse LIMIT ?",
        (q, limit)).fetchall()
    con.close()
    return [(r["ref"], r["text"]) for r in rows]


def count(db_path: Path | str = DB) -> int:
    con = _con(db_path)
    n = con.execute("SELECT COUNT(*) AS n FROM verses").fetchone()["n"]
    con.close()
    return n


def main():
    n = build_db()
    print(f"Watchman KJV archive built: {n:,} verses "
          f"({'OK' if n == TOTAL_VERSES else 'WRONG COUNT'})")
    print("  John 3:16 :", verse("John", 3, 16))
    hits = search_verbatim("the Word was God")
    print(f"  verbatim search 'the Word was God' -> {len(hits)} hit(s): {hits[0][0] if hits else '-'}")


if __name__ == "__main__":
    main()
