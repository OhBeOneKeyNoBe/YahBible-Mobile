#!/usr/bin/env python3
r"""o_taviel_server.py -- O'Tav'iel: the Tav'iel biblical-research app server (the
ROOT instance). Serves the 3-panel research UI + a JSON API over the REAL data:
KJV (Watchman, 31,102 verses), extra public-domain versions (getBible: WEB/ASV/
YLT/...), the reflected_red lexical torus (Strong's, Greek/Hebrew/Aramaic
interlinear, lexicon definitions -- indexed lookups only), the Enoch books, the
composed gnostic Book, the Yahweh Tsidkenu keys, and the DIGESTED apocrypha
corpora (Ethiopian, Gnostic Bible, Nag Hammadi) organized Book -> Chapter -> Verse.

Clean definitions (biblical languages only, real glosses -- no raw JSON/foreign
noise), clickable Strong's numbers, per-verse version comparison, and chapter
indexes for every book. Local, 127.0.0.1:41537.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

_APPDIR = os.path.dirname(os.path.abspath(__file__))
if _APPDIR not in sys.path:
    sys.path.insert(0, _APPDIR)                       # a self-contained (C:) install wins over the dev tree
for _dev in (os.path.join(_APPDIR, "watchman"), r"D:\Holorites\torus_upgrades", r"D:\watchman"):
    if os.path.isdir(_dev) and _dev not in sys.path:
        sys.path.append(_dev)                         # bundled watchman / the D: dev tree = fallback only
from o_taviel_ui import PAGE  # noqa: E402

# The Lovable web app is the source-of-truth UI. When present, O'Tav'iel serves that
# exact interface (index.html + shim/*) in NATIVE mode (window.YB_NATIVE) so /api
# still hits this real Python backend, instead of its own legacy PAGE. Set
# YAHBIBLE_NATIVE_UI=0 to fall back to the legacy PAGE.
LOVABLE_UI_DIR = os.environ.get("YAHBIBLE_LOVABLE_DIR", r"D:\creator-connect\public\yahbible-app")
LOVABLE_UI = os.environ.get("YAHBIBLE_NATIVE_UI", "1") != "0" and \
    os.path.isfile(os.path.join(LOVABLE_UI_DIR, "index.html"))
_LOVABLE_CT = {".js": "application/javascript", ".mjs": "application/javascript",
               ".css": "text/css", ".json": "application/json", ".webmanifest": "application/json",
               ".wasm": "application/wasm", ".html": "text/html; charset=utf-8",
               ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".webp": "image/webp", ".svg": "image/svg+xml", ".gif": "image/gif",
               ".mp4": "video/mp4", ".webm": "video/webm", ".woff2": "font/woff2",
               ".ico": "image/x-icon", ".tflite": "application/octet-stream",
               ".binarypb": "application/octet-stream", ".data": "application/octet-stream"}

_MOBILE_PING = {}   # {"ts","name"}: last YahBible-mobile ping, for the two-way sync indicator

# GitHub vault sync: a PRIVATE repo carries profile/settings/progress across devices.
# The token lives in a LOCAL file (or env), never in any repo or shipped bundle.
GH_SYNC_REPO = "OhBeOneKeyNoBe/YahBible-Sync"
GH_TOKEN_FILE = r"D:\Holorites_data\gh_sync_token.txt"


def _gh_token():
    tok = os.environ.get("YAHBIBLE_GH_TOKEN", "")
    if not tok:
        try:
            if os.path.isfile(GH_TOKEN_FILE):
                tok = open(GH_TOKEN_FILE, encoding="utf-8").read().strip()
        except Exception:
            tok = ""
    return tok


# ---- brute-force throttle: per (ip, username), 8 failures = 60s lockout ----
_LOGIN_FAILS = {}


def _throttle_check(key):
    c, until = _LOGIN_FAILS.get(key, (0, 0))
    if until > time.time():
        return int(until - time.time()) or 1
    return 0


def _throttle_hit(key, ok):
    if ok:
        _LOGIN_FAILS.pop(key, None)
        return
    c, until = _LOGIN_FAILS.get(key, (0, 0))
    c += 1
    _LOGIN_FAILS[key] = (c, time.time() + 60 if c >= 8 else 0)


# ---- vault encryption: AES-256-GCM with a key derived (PBKDF2, 200k) from a passphrase
# that lives ONLY in a local file / env — so even a leaked repo + token yields ciphertext ----
VAULT_KEY_FILE = r"D:\Holorites_data\vault_key.txt"


def _vault_pass():
    ph = os.environ.get("YAHBIBLE_VAULT_PASS", "")
    if not ph:
        try:
            if os.path.isfile(VAULT_KEY_FILE):
                ph = open(VAULT_KEY_FILE, encoding="utf-8").read().strip()
        except Exception:
            ph = ""
    return ph


def _vault_encrypt(obj):
    ph = _vault_pass()
    if not ph:
        return obj
    import base64 as b64
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    salt = os.urandom(16)
    key = _hl.pbkdf2_hmac("sha256", ph.encode("utf-8"), salt, 200000)
    iv = os.urandom(12)
    ct = AESGCM(key).encrypt(iv, json.dumps(obj, ensure_ascii=False).encode("utf-8"), b"yahbible-vault")
    return {"enc": 1, "kind": obj.get("kind", "yahbible-sync"),
            "salt": b64.b64encode(salt).decode(), "iv": b64.b64encode(iv).decode(),
            "ct": b64.b64encode(ct).decode()}


def _vault_decrypt(obj):
    if not (isinstance(obj, dict) and obj.get("enc")):
        return obj
    ph = _vault_pass()
    if not ph:
        raise ValueError("the vault is encrypted and this machine has no passphrase")
    import base64 as b64
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = _hl.pbkdf2_hmac("sha256", ph.encode("utf-8"), b64.b64decode(obj["salt"]), 200000)
    pt = AESGCM(key).decrypt(b64.b64decode(obj["iv"]), b64.b64decode(obj["ct"]), b"yahbible-vault")
    return json.loads(pt.decode("utf-8"))


def _registry_publish():
    """Mirror a SANITIZED account registry to the private vault (background, best-effort):
    usernames + sha256 of the email + created time. Passwords and plaintext emails never leave
    the Zion'iel Network node."""
    def run():
        try:
            import base64
            import hashlib as hl
            import urllib.request
            tok = _gh_token()
            if not tok:
                return
            con = _c(USERS_RO)
            rows = con.execute("SELECT username,email,created FROM users WHERE is_guest=0").fetchall()
            con.close()
            reg = {"kind": "yahbible-registry", "ts": int(time.time() * 1000),
                   "users": [{"name": r[0],
                              "email_sha": (hl.sha256(r[1].strip().lower().encode()).hexdigest() if r[1] else ""),
                              "created": int(r[2] or 0)} for r in rows]}
            url = "https://api.github.com/repos/%s/contents/registry.json" % GH_SYNC_REPO
            hdrs = {"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json",
                    "User-Agent": "yahbible", "Content-Type": "application/json"}
            sha = None
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=hdrs), timeout=20) as r0:
                    sha = json.loads(r0.read().decode()).get("sha")
            except Exception:
                sha = None
            body = {"message": "registry update",
                    "content": base64.b64encode(json.dumps(_vault_encrypt(reg)).encode()).decode()}
            if sha:
                body["sha"] = sha
            urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(body).encode(),
                                                          method="PUT", headers=hdrs), timeout=30).read()
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()


def gh_sync(username, direction):
    """Push/pull this user's profile + reading progress to/from the private GitHub vault.
    Merging, never clobbering: progress is a union; profile fields overwrite only when set.
    Credentials are NEVER written to the vault."""
    import base64
    import urllib.error
    import urllib.request
    tok = _gh_token()
    if not tok:
        return {"ok": False, "error": "no GitHub token — put one in " + GH_TOKEN_FILE}
    if not username:
        return {"ok": False, "error": "sign in first"}
    safe = re.sub(r"[^a-z0-9_.-]", "_", username.lower())
    url = "https://api.github.com/repos/%s/contents/sync/%s.json" % (GH_SYNC_REPO, safe)
    hdrs = {"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json",
            "User-Agent": "yahbible", "Content-Type": "application/json"}

    def req(method, body=None):
        r = urllib.request.Request(url, data=(json.dumps(body).encode() if body else None),
                                   method=method, headers=hdrs)
        try:
            with urllib.request.urlopen(r, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            return {"__err": "GitHub %d" % e.code}

    f = req("GET")
    if isinstance(f, dict) and f.get("__err"):
        return {"ok": False, "error": f["__err"]}
    remote = {}
    if f:
        try:
            remote = json.loads(base64.b64decode(f.get("content", "")).decode("utf-8")) or {}
        except Exception:
            remote = {}
        try:
            remote = _vault_decrypt(remote)   # encrypted vault: decrypt with the local passphrase
        except Exception as e:
            return {"ok": False, "error": "vault decrypt failed — " + str(e)[:80]}
    if direction == "pull":
        if not remote:
            return {"ok": False, "error": "nothing in the vault yet — Save from a device first"}
        prof = remote.get("profile") or {}
        n = 0
        with _ULOCK:
            con = sqlite3.connect(USERS_RW); con.execute("PRAGMA busy_timeout=8000")
            if prof:
                con.execute("UPDATE users SET name=COALESCE(NULLIF(?,''),name),"
                            " bio=COALESCE(NULLIF(?,''),bio), avatar=COALESCE(NULLIF(?,''),avatar)"
                            " WHERE username=?",
                            (prof.get("name", ""), prof.get("bio", ""), prof.get("avatar", ""), username))
            for ref in remote.get("progress") or []:
                if isinstance(ref, str) and "|" in ref:
                    con.execute("INSERT OR IGNORE INTO progress VALUES(?,?,?)", (username, ref, time.time()))
                    n += 1
            con.commit(); con.close()
        return {"ok": True, "pulled": n, "profile": bool(prof)}
    # push: merge over what is there
    con = _c(USERS_RO)
    row = con.execute("SELECT name,bio,avatar,social FROM users WHERE username=?", (username,)).fetchone()
    refs = [r[0] for r in con.execute("SELECT ref FROM progress WHERE username=?", (username,))]
    con.close()
    remote["kind"] = "yahbible-sync"
    remote["ts"] = int(time.time() * 1000)
    p = remote.get("profile") or {}
    if row:
        if row[0]:
            p["name"] = row[0]
        if row[1]:
            p["bio"] = row[1]
        if row[2]:
            p["avatar"] = row[2]
        if row[3]:
            try:
                p["social"] = json.loads(row[3])
            except Exception:
                pass
    remote["profile"] = p
    remote["progress"] = sorted(set([x for x in (remote.get("progress") or []) if isinstance(x, str)] + refs))
    body = {"message": "YahBible desktop sync",
            "content": base64.b64encode(json.dumps(_vault_encrypt(remote), ensure_ascii=False).encode("utf-8")).decode()}
    if f and f.get("sha"):
        body["sha"] = f["sha"]
    out = req("PUT", body)
    if isinstance(out, dict) and out.get("__err"):
        return {"ok": False, "error": out["__err"]}
    return {"ok": True, "pushed": len(remote["progress"])}
from taviel_book_hebrew import BOOK_HEBREW  # noqa: E402
try:
    import taviel_updates as TU  # noqa: E402  (Origin-signed, hash-verified network updates)
except Exception:                # phone / minimal install without the cryptography wheel:
    class _TUUnavailable:        # the app runs whole; only the update endpoints decline
        def __getattr__(self, _k):
            def _f(*_a, **_kw):
                return {"ok": False, "error": "updates unavailable on this platform"}
            return _f
    TU = _TUUnavailable()  # type: ignore

# Relocatable data base: the SHIPPED app sets YAHBIBLE_BASE to its downloaded library dir;
# unset (this dev machine) falls back to "D:" so every path below is byte-identical to before.
_YB = os.environ.get("YAHBIBLE_BASE", "D:").replace("\\", "/").rstrip("/")
_DEVDIR = r"D:\Holorites\torus_upgrades"
def _res(fname):
    """Resolve an app asset (json / txt / dir): prefer the local app dir (a self-contained C:
    install), then the YAHBIBLE_BASE tree, then the D: dev tree (skipped when YAHBIBLE_NO_D is set,
    which is how we prove the app runs with no external drive)."""
    cands = [os.path.join(_APPDIR, fname),
             ("%s/Holorites/torus_upgrades/%s" % (_YB, fname)).replace("/", os.sep)]
    _cd = os.environ.get("YAHBIBLE_CODE")         # auto-updated code/data pulled from the repo
    if _cd:
        cands.insert(0, os.path.join(_cd, fname))
    _mp = getattr(sys, "_MEIPASS", None)          # frozen exe: assets bundled at the PyInstaller root
    if _mp:
        cands.insert(0, os.path.join(_mp, fname))
    if not os.environ.get("YAHBIBLE_NO_D"):
        cands.append(os.path.join(_DEVDIR, fname))
    for c in cands:
        if os.path.exists(c):
            return c
    return cands[0]
WATCHMAN = "file:%s/watchman/watchman.db?mode=ro" % _YB
# Lexicon (interlinear + Strong's + dictionary). Prefer the full 70GB if it sits under the app's
# base; else the compact distilled basics; else (drive present) the D: dev copy -- so interlinear
# works whenever the lexicon is reachable, and degrades gracefully (empty) when it is not.
_lex_full = "%s/Holorites_data/reflected_red.sqlite" % _YB
_lex_basic = "%s/Holorites_data/daeos/reflected_red_basic.sqlite" % _YB
_lex_cands = [_lex_full, _lex_basic]
if not os.environ.get("YAHBIBLE_NO_D"):
    _lex_cands.append("D:/Holorites_data/reflected_red.sqlite")
_lexfile = next((p for p in _lex_cands
                 if os.path.exists(p.replace("/", os.sep)) and os.path.getsize(p.replace("/", os.sep)) > 0), None)
LEX = "file:%s?mode=ro" % (_lexfile or (_lex_full + "#absent"))
ENOCH = "file:%s/Holorites/torus_upgrades/enoch_source.sqlite?mode=ro" % _YB
YT = "file:%s/Holorites_data/daeos/elaniel_yt.sqlite?mode=ro" % _YB
VERSIONS_DB = "file:%s/Holorites_data/daeos/taviel_versions.sqlite?mode=ro" % _YB
CORPUS_DB = "file:%s/Holorites_data/daeos/taviel_corpus.sqlite?mode=ro" % _YB
ENGLISH_DB = "file:%s/Holorites_data/daeos/english_dict.sqlite?mode=ro" % _YB   # offline WordNet dictionary
PIPER_VOICE = ("%s/Holorites_data/daeos/piper/en_US-lessac-medium.onnx" % _YB).replace("/", os.sep)  # offline TTS
YT_RW = (_YB + "/Holorites_data/daeos/elaniel_yt.sqlite").replace("/", os.sep)  # writable nexus (conclusions)
USERS_RW = (_YB + "/Holorites_data/daeos/taviel_users.sqlite").replace("/", os.sep)  # accounts + per-user notes
USERS_RO = "file:%s/Holorites_data/daeos/taviel_users.sqlite?mode=ro" % _YB
_WLOCK = threading.Lock()
_ULOCK = threading.Lock()
import hashlib as _hl  # noqa: E402
ASSETS = _res("taviel_assets")
PORT = 41537
CORPUS_TITLES = {"ethiopian_apocrypha": "Ethiopian Apocrypha",
                 "gnostic_bible": "The Gnostic Bible", "nag_hammadi": "The Nag Hammadi Library",
                 "yahweh_tsidkenu_full": "Yahweh Tsidkenu -- Complete Knowledge",
                 "quran": "The Qur'an",
                 "mishnah": "The Mishnah", "tosefta": "The Tosefta", "talmud": "The Talmud",
                 "targum": "The Targums", "midrash": "Midrash", "kabbalah": "Kabbalah & Hekhalot",
                 "second_temple": "Second Temple & Apocrypha", "apostolic": "Apostolic & Patristic",
                 "mandaean": "Mandaean Scriptures", "manichaean": "Manichaean Texts",
                 "josephus": "Josephus (Whiston)", "torah": "The Torah",
                 "christian": "Ante-Nicene Fathers",
                 "pistis_sophia": "Pistis Sophia",
                 "dss": "Dead Sea Scrolls (Hebrew/Aramaic)",
                 "redletter": "Red Letter Words"}
# corpora ingested from Sefaria carry a parallel Hebrew original (sefaria_hebrew table) ->
# English is the default text, an 'orig' toggle shows the Hebrew.
SEFARIA_CORPORA = {"mishnah", "tosefta", "talmud", "targum", "midrash", "kabbalah",
                   "second_temple", "torah"}
# the two PD Lidzbarski Mandaean books: English (machine translation) default in corpus_units,
# German original toggled from the mandaean_orig table.
MAND_DE_BOOKS = {"Ginza Rabba — the Great Treasure", "Das Johannesbuch der Mandäer"}
# prose anthologies/books -> read continuously, no artificial verse markers.
# (the Ethiopian Apocrypha keeps its real [1][2] verse structure.)
PROSE_CORPORA = {"yahweh_tsidkenu_full", "gnostic_bible"}
# gnostic_bible still carries OCR apparatus and needs heuristic cleaning; nag_hammadi
# was re-ingested WORD-EXACT from the source PDF, so it is served verbatim (versified).
CLEAN_CORPORA = {"gnostic_bible"}
# languages worth showing in a BIBLICAL research tool (drop Wiktionary's Old Norse,
# Czech, Frisian, Scots ... noise that made definitions look disorganized)
KEEP_LANG = {"en", "eng", "he", "heb", "grc", "gk", "el", "greek", "hebrew",
             "arc", "aramaic", "la", "lat", "latin"}
LANG_NAME = {"he": "Hebrew", "heb": "Hebrew", "grc": "Greek", "gk": "Greek",
             "el": "Greek", "arc": "Aramaic", "la": "Latin", "lat": "Latin",
             "en": "English", "eng": "English"}
_LOCAL = threading.local()


class _NullConn:
    """Stand-in for a database that is absent or invalid (e.g. the optional 70GB lexicon is
    not installed): every query yields nothing instead of raising, so the app keeps working
    (word study falls back to transliteration/gematria/glossary; the reader is unaffected)."""
    def execute(self, *a, **k):
        return self
    def executescript(self, *a, **k):
        return self
    def cursor(self):
        return self
    def fetchall(self):
        return []
    def fetchmany(self, *a, **k):
        return []
    def fetchone(self):
        return None
    def __iter__(self):
        return iter(())
    def commit(self):
        pass
    def close(self):
        pass


_NULL = _NullConn()


def _c(uri):
    """Per-thread cached read-only connections (fast, no re-open). A missing or invalid database
    (0-byte, not-a-db, drive absent) resolves to a null connection so callers never crash."""
    cache = getattr(_LOCAL, "conns", None)
    if cache is None:
        cache = _LOCAL.conns = {}
    if uri not in cache:
        try:
            conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
            conn.execute("SELECT 1 FROM sqlite_master LIMIT 1")   # validate: catches 0-byte / not-a-db
            cache[uri] = conn
        except sqlite3.Error:
            cache[uri] = _NULL
    return cache[uri]


# ---- definition parsing (clean) ----------------------------------------------
def _clean_markup(t):
    """Turn raw Thayer/Abbott-Smith lexicon markup into readable prose: <ref='..'>X</ref> -> X,
    <BR /> -> a break, strip <b>/<i>/other tags, '__1.' sense-markers, dagger and source tags."""
    if not t:
        return t
    t = str(t)
    t = re.sub(r"<ref[^>]*>(.*?)</ref>", r"\1", t, flags=re.S | re.I)   # keep the citation text
    t = re.sub(r"<\s*br\s*/?\s*>", " — ", t, flags=re.I)               # <BR /> -> a light break
    t = re.sub(r"</?[a-zA-Z][^>]*>", "", t)                            # strip remaining tags
    t = re.sub(r"\s*__+\s*", " ", t)                                   # '__1.' numbered-sense markers
    t = t.replace("†", "").replace("‡", "")                            # dagger markers
    t = re.sub(r"\(\s*(AS|Rec\.?|Tr\.?|WH|L|LXX only)\s*\)\s*$", "", t)   # trailing source tags
    t = re.sub(r"^\s*(?:—\s*)+", "", t)                                # leading break
    t = re.sub(r"\s+([;,.:])", r"\1", t)                              # tidy space-before-punct
    t = re.sub(r"(—\s*)+$", "", t)                                     # trailing break
    return re.sub(r"\s{2,}", " ", t).strip()


def _gloss_from(rec):
    """Extract a CLEAN gloss + part-of-speech from a lexical source_record.
    Returns (gloss_or_None, pos). Never returns raw JSON or usage examples."""
    if not rec:
        return None, ""
    rec = rec.strip()
    if not rec.startswith("{"):
        # STEP lexicon rows are tab-separated: sid, "sid =", sid, glyph, translit, POS, gloss...
        # keep only the actual gloss (everything after the POS field), not the sid/glyph prefix
        if "\t" in rec:
            parts = rec.split("\t")
            for i, p in enumerate(parts):
                if re.match(r"^[HG]:", p.strip()):
                    tail = [x.strip() for x in parts[i + 1:] if x.strip()]
                    if tail:
                        return (_clean_markup(" ; ".join(dict.fromkeys(tail))[:400]) or None), p.strip()
                    break
        return (_clean_markup(rec[:400]) or None), ""
    try:
        j = json.loads(rec)
    except Exception:
        return None, ""
    pos = (j.get("part_of_speech") or j.get("pos") or "").strip()
    d = j.get("definition") or j.get("strongs_def") or j.get("meaning")
    if d and str(d).strip():
        return _clean_markup(str(d).strip()), pos
    gl = []
    for s in (j.get("senses") or []):
        for g in (s.get("glosses") or []):
            if g and g not in gl:
                gl.append(g)
    for g in (j.get("glosses") or []):
        if g and g not in gl:
            gl.append(g)
    if gl:
        return _clean_markup("; ".join(gl[:3])), pos
    return None, pos


def _norm_lang(lang):
    return (lang or "").lower().split("-")[0].strip()


# openscriptures Strong's dictionary (translit/pron/definition) -- fills the gaps
# where the local lexicon has no English/pronunciation for a Strong's number.
_STRONGS_EXT = None
_STRONGS_EXT_PATH = _res("taviel_strongs.json")


def _ext(sid):
    global _STRONGS_EXT
    if _STRONGS_EXT is None:
        try:
            with open(_STRONGS_EXT_PATH, encoding="utf-8") as f:
                _STRONGS_EXT = json.load(f)
        except Exception:
            _STRONGS_EXT = {}
    if not sid:
        return {}
    m = re.match(r"^([HG])0*(\d+)", sid.strip(), re.I)   # G0026 -> G26 ; H0430 -> H430
    key = (m.group(1).upper() + m.group(2)) if m else sid
    return _STRONGS_EXT.get(key, {})


def _ext_def(sid):
    e = _ext(sid)
    return _clean_markup((e.get("def") or e.get("kjv") or "").strip())


def _ext_pron(sid):
    e = _ext(sid)
    return (e.get("p") or e.get("x") or "").strip()


# Sword/getBible markup leaks into some translations (YLT etc): <FI>added<Fi>
# (translator-added words), <RF>..<Rf> (footnotes), <TS>..<Ts> (titles), <CM>/<PF>..
_MARKUP = re.compile(r"<RF>.*?<Rf>|<TS>.*?<Ts>|<[^>]{0,40}>", re.S | re.I)


def _clean(text):
    if not text:
        return text
    return re.sub(r"\s+", " ", _MARKUP.sub("", text)).strip()


# ---- data helpers -------------------------------------------------------------
def books():
    c = _c(WATCHMAN)
    return [r[0] for r in c.execute("SELECT DISTINCT book FROM verses ORDER BY book_order")]


def kjv_chapters(book):
    c = _c(WATCHMAN)
    return [r[0] for r in c.execute("SELECT DISTINCT chapter FROM verses WHERE book=?"
            " ORDER BY chapter", (book,))]


def versions_available():
    """KJV first, then English translations, then the rest -- alphabetical within."""
    v = ["KJV"]
    d = _c(VERSIONS_DB)
    if d is not None:
        try:
            rows = d.execute("SELECT v.version, COALESCE(m.language,'') FROM"
                             " (SELECT DISTINCT version FROM verses) v"
                             " LEFT JOIN versions_meta m ON m.version=v.version").fetchall()
            def rank(lang):
                return 0 if (lang or "").lower() == "english" else 1
            for ver in sorted(rows, key=lambda r: (rank(r[1]), r[0].lower())):
                if ver[0] not in v:
                    v.append(ver[0])
        except sqlite3.OperationalError:
            try:
                v += [r[0] for r in d.execute("SELECT DISTINCT version FROM verses ORDER BY version")]
            except sqlite3.OperationalError:
                pass
    return v


APOC_BASE = [
    {"id": "enoch1", "title": "1 Enoch (Ethiopic)"},
    {"id": "enoch2", "title": "2 Enoch (Slavonic)"},
    {"id": "enoch3", "title": "3 Enoch (Hebrew)"},
]
# "Gnosis: The Eternal Mirror" (gnosis_book) and the "Nine Keys" (yahweh_tsidkenu)
# are Incarnate-only -- NOT listed in O'Tav'iel / Tav'iel, nor surfaced in Revelation.


def apocrypha_menu():
    """Base apocrypha + any digested PDF corpora present in the corpus store."""
    items = list(APOC_BASE)
    d = _c(CORPUS_DB)
    if d is not None:
        try:
            for (cid,) in d.execute("SELECT DISTINCT corpus FROM corpus_units"):
                if cid == "yahweh_tsidkenu_full":   # removed from O'Tav'iel at Elan'iel's direction
                    continue
                items.append({"id": "corpus:" + cid, "title": CORPUS_TITLES.get(cid, cid)})
        except sqlite3.OperationalError:
            pass
    return items


def chapter(book, ch, version="KJV"):
    if version and version != "KJV":
        d = _c(VERSIONS_DB)
        if d is not None:
            rows = d.execute("SELECT verse,text FROM verses WHERE version=? AND book=?"
                             " AND chapter=? ORDER BY verse", (version, book, ch)).fetchall()
            if rows:
                return {"cite": "%s -- %s %d" % (version, book, ch),
                        "verses": [{"verse": r[0], "text": _clean(r[1])} for r in rows]}
    c = _c(WATCHMAN)
    rows = c.execute("SELECT verse,text FROM verses WHERE book=? AND chapter=? ORDER BY verse",
                     (book, ch)).fetchall()
    return {"cite": "King James Version &middot; %s %d" % (book, ch),
            "verses": [{"verse": r[0], "text": r[1]} for r in rows]}


def _version_langs():
    d = _c(VERSIONS_DB)
    langs = {"KJV": "English"}
    if d is not None:
        try:
            for v, lang in d.execute("SELECT version,language FROM versions_meta"):
                langs[v] = lang or "Other"
        except sqlite3.OperationalError:
            pass
    return langs


def verse_versions(book, ch, verse):
    """The SAME verse across every available version (for per-verse comparison),
    each tagged with its language so the UI can default to English."""
    langs = _version_langs()
    out = []
    c = _c(WATCHMAN)
    r = c.execute("SELECT text FROM verses WHERE book=? AND chapter=? AND verse=?",
                  (book, ch, verse)).fetchone()
    if r:
        out.append({"version": "KJV", "text": r[0], "language": "English"})
    d = _c(VERSIONS_DB)
    if d is not None:
        try:
            for ver, txt in d.execute("SELECT version,text FROM verses WHERE book=? AND"
                    " chapter=? AND verse=? ORDER BY version", (book, ch, verse)):
                out.append({"version": ver, "text": _clean(txt), "language": langs.get(ver, "Other")})
        except sqlite3.OperationalError:
            pass
    return {"ref": "%s %d:%d" % (book, ch, verse), "versions": out}


def versions_meta():
    langs = _version_langs()
    return {"versions": [{"version": v, "language": langs.get(v, "Other")}
                         for v in versions_available()]}


def languages_available():
    langs = _version_langs()
    uniq = sorted(set(langs.values()), key=lambda x: (0 if x == "English" else 1, x))
    return {"languages": uniq}


def _looks_like_namedb(g):
    """STEPBible proper-name records leak as 'Levi@Luk.3.24=G3017 ...' -- reject."""
    return bool(re.search(r"@[A-Za-z]{2,3}\.\d|=[GH]\d{2,}", g or ""))


def _orig_script(g):
    """True only if the glyph actually contains Hebrew or Greek letters."""
    return any("֐" <= ch <= "׿" or "Ͱ" <= ch <= "Ͽ" for ch in (g or ""))


def _original_for(c, strong_addr):
    """A representative original-language glyph + token sid for a Strong's entry
    (so the English word can show its Hebrew/Greek form, clickable to deep study)."""
    try:
        tok = c.execute("SELECT n.source_id,n.canonical_lemma FROM lexical_routes r"
                        " JOIN lexical_nodes n ON n.address24=r.source_address24 WHERE"
                        " r.target_address24=? AND r.relation_type='strongs' LIMIT 1",
                        (strong_addr,)).fetchone()
    except sqlite3.OperationalError:
        tok = None
    return tok  # (sid, glyph) or None


_APOC_GLOSS = None
_APOC_VARIDX = None
_ALIASES = None


def _fold(w):
    """Fold Latin diacritics to ASCII so accented transliterations match (Araqiêl->araqiel,
    Kôkabêl->kokabel)."""
    import unicodedata
    return unicodedata.normalize("NFKD", w or "").encode("ascii", "ignore").decode().lower()


def _alias(w):
    """Manual spelling corrections (transpositions the fuzzy key can't catch, e.g.
    Badariel->Baradiel), from taviel_aliases.json."""
    global _ALIASES
    if _ALIASES is None:
        try:
            _ALIASES = {k.lower(): v.lower() for k, v in json.load(
                open(_res("taviel_aliases.json"), encoding="utf-8")).items()}
        except Exception:
            _ALIASES = {}
    return _ALIASES.get((w or "").lower().strip(), w)


def _variant_key(w):
    """A fuzzy consonant-skeleton key so alternative transliterations of the same word
    collide: Yeshiba~Yeshivah, Raqiaf~Raqia, Chalkadri~Chalkidri. Folds the common
    Hebrew-transliteration equivalences (v/b, k/c/q, z/s, ph/f, th/t), drops h, vowels
    (except the first letter) and doubled letters."""
    import re as _re
    s = _re.sub(r"[^a-z]", "", (w or "").lower())
    if len(s) < 3:
        return ""
    s = s.replace("ph", "f").replace("th", "t").replace("sh", "S").replace("ch", "K")
    s = s.translate(str.maketrans({"v": "b", "w": "b", "k": "K", "q": "K", "c": "K",
                                   "z": "s", "x": "s", "j": "y"}))
    s = s.replace("h", "")
    head, rest = s[0], _re.sub(r"[aeiouy]", "", s[1:])
    s = _re.sub(r"(.)\1+", r"\1", head + rest)
    return s


def _apoc_glossary_sense(w):
    """Definition for an Ethiopian-apocrypha / Enoch proper noun or term (Meqabees, JAH,
    Gehannem, Raqia, Metatron...). Exact first; then a variant-spelling fallback so an
    alternative transliteration still returns the canonical word's definition."""
    global _APOC_GLOSS, _APOC_VARIDX
    if _APOC_GLOSS is None:
        _APOC_GLOSS = {}
        _APOC_VARIDX = {}
        for path in (_res("taviel_apoc_glossary.json"), _res("taviel_enoch_glossary.json"),
                     _res("taviel_enoch_full.json"), _res("taviel_enoch_supp.json"),
                     _res("taviel_enoch_names.json")):
            try:
                for k, v in json.load(open(path, encoding="utf-8")).items():
                    _APOC_GLOSS.setdefault(k.lower(), v)
                    _APOC_GLOSS.setdefault(_fold(k), v)       # accent-folded key too
                    vk = _variant_key(k)
                    if vk:
                        _APOC_VARIDX.setdefault(vk, (k.lower(), v))
            except Exception:
                pass
    lw = _alias((w or "").lower().strip())
    g = _APOC_GLOSS.get(lw)
    note = ""
    # fuzzy/variant matching is ONLY for non-dictionary words (proper nouns, transliterations);
    # an ordinary English word like 'source' keeps its own dictionary meaning, never a fuzzy glossary hit.
    if not g and lw not in _wordset():
        g = _APOC_GLOSS.get(_fold(w))
        if not g:
            hit = _APOC_VARIDX.get(_variant_key(lw)) or _APOC_VARIDX.get(_variant_key(_fold(w)))
            if hit and hit[0] != lw:
                g, note = hit[1], "(as the spelling “%s”) " % hit[0]
    if not g:
        return None
    return {"pos": g.get("type") or "term", "gloss": note + (g.get("def") or ""),
            "lang": "Ethiopian"}


def _glossary_sense(w):
    try:
        import taviel_glossary as GL
        s = GL.define(w)
        if s:
            return s
    except Exception:
        pass
    return _apoc_glossary_sense(w)


def _singular_candidates(w):
    """Singular / variant forms to fall back on so a PLURAL carries its singular's
    definition ('parasanges'/'parasange' -> 'parasang', 'cherubim' -> 'cherub')."""
    w = (w or "").lower()
    out = []
    if w.endswith("'s") or w.endswith("’s"):        # possessive -> base word
        out.append(w[:-2])
    if (w.endswith("'") or w.endswith("’")) and len(w) > 3:
        out.append(w[:-1])
    if w.endswith("ies") and len(w) > 4:
        out.append(w[:-3] + "y")
    if w.endswith("es") and len(w) > 3:
        out.append(w[:-2])
    if w.endswith("s") and len(w) > 3:
        out.append(w[:-1])
    if w.endswith("e") and len(w) > 3:      # 'parasange' -> 'parasang'
        out.append(w[:-1])
    if w.endswith("im") and len(w) > 4:     # Hebrew masculine plural
        out.append(w[:-2])
    if w.endswith("oth") and len(w) > 4:    # Hebrew feminine plural
        out.append(w[:-3])
    seen = set()
    return [x for x in out if not (x in seen or seen.add(x))]


def _is_stub(gloss):
    """A cross-reference gloss ('plural of parasang', 'see X', 'variant of Y') that is not
    itself a real definition -- so we should also fetch the referenced word's meaning."""
    g = (gloss or "").strip().lower()
    return bool(re.match(r"^(a\s+)?(plural|pl\.?|sing(ular)?\.?|variant|var\.?|form|inflection"
                         r"|see|cf\.?|compare)\b", g)) and len(g) < 60


def _fallback_senses(w):
    """Senses of a singular/variant form of w, each noted as such (no recursion)."""
    for cand in _singular_candidates(w):
        sub = word_lookup(cand, _fb=False)
        subs = (sub or {}).get("senses") or []
        if subs:
            out = []
            for s in subs:
                s2 = dict(s)
                s2["gloss"] = "(plural/variant of “%s”) %s" % (cand, s2.get("gloss", ""))
                out.append(s2)
            return out
    return []


def _looks_like_morph(rec):
    """A raw (non-JSON) STEP interlinear / Ketiv-Qere morphology record -- NOT a
    dictionary sense. These leak in as garbage 'definitions' (e.g. 'Gen.1.1#04=L ...
    K= ''et (אֵת) ... ¦; H0853 hebrew') and must never be shown as a word's meaning."""
    if not rec:
        return False
    r = rec.strip()
    if r.startswith("{"):
        return False   # a real JSON dictionary record
    return ("¦" in r) or ("=Q(" in r) or (" L= " in r) or (" K= " in r) or bool(re.search(r"#\d+=", r))


def word_lookup(w, _fb=True):
    """Indexed lemma lookup -> CLEAN, biblically-relevant definition.
    Returns the original (Hebrew/Greek) forms + Strong's + English senses; no foreign
    noise and no proper-name-database junk. A gnostic-glossary sense (if any) is shown
    first, and covers special terms/identities the lexicon lacks (e.g. Barbelo).
    When a word yields no definition, its singular/variant is tried so a plural carries
    the singular's meaning ('parasanges' -> 'parasang')."""
    c = _c(LEX)
    try:
        rows = c.execute("SELECT address24,node_type,source_id,language,source_record FROM"
                         " lexical_nodes INDEXED BY idx_nodes_lemma WHERE canonical_lemma=?"
                         " LIMIT 60", (w,)).fetchall()
    except sqlite3.OperationalError:
        rows = []   # lexicon absent (phone / portable): glossary + WordNet + Strong's json carry it
    if not rows:
        gs = _glossary_sense(w)
        senses0 = [gs] if gs else []
        if _fb and not senses0:
            senses0 = _fallback_senses(w)
        if senses0:
            return {"found": True, "word": w, "address24": None, "originals": [],
                    "strongs": [], "senses": senses0}
        return {"found": False, "word": w}
    addr = rows[0][0]
    strongs, senses, seen_gloss = [], [], set()
    for a, nt, sid, lang, rec in rows:
        nl = _norm_lang(lang)
        gloss, pos = _gloss_from(rec)
        if nt == "strongs_entry":
            sid_num = sid.split(":")[-1]
            strongs.append({"id": sid_num, "addr": a,
                            "language": LANG_NAME.get(nl, nl or "?"),
                            "pos": pos, "definition": gloss or _ext_def(sid_num)})
            continue
        if nl not in KEEP_LANG:      # drop Old Norse / Czech / Frisian ... noise
            continue
        if not gloss or _looks_like_namedb(gloss) or _looks_like_morph(rec):
            continue
        key = gloss.lower()[:60]
        if key in seen_gloss:
            continue
        seen_gloss.add(key)
        senses.append({"pos": pos, "gloss": gloss, "lang": LANG_NAME.get(nl, nl)})
        if len(senses) >= 8:
            break
    # guarantee Strong's entries even when they fall outside the first 60 rows
    if not strongs:
        try:
            for a, sid, lang, rec in c.execute(
                    "SELECT address24,source_id,language,source_record FROM lexical_nodes"
                    " INDEXED BY idx_nodes_lemma WHERE canonical_lemma=? AND"
                    " node_type='strongs_entry' LIMIT 8", (w,)):
                g, pos = _gloss_from(rec)
                strongs.append({"id": sid.split(":")[-1], "addr": a,
                                "language": LANG_NAME.get(_norm_lang(lang), lang or "?"),
                                "pos": pos, "definition": g or _ext_def(sid.split(":")[-1])})
        except sqlite3.OperationalError:
            pass
    # dedupe Strong's (Hebrew first), attach a clickable original glyph, clean junk
    ded, sids, originals = [], set(), []
    for s in sorted(strongs, key=lambda x: (0 if x["id"].startswith("H") else 1)):
        if s["id"] in sids:
            continue
        sids.add(s["id"])
        tok = _original_for(c, s["addr"])
        if tok and _orig_script(tok[1]):
            s["glyph"] = _ng(tok[1]); s["sid"] = tok[0]
            originals.append({"glyph": _ng(tok[1]), "sid": tok[0], "id": s["id"],
                              "language": s["language"]})
        if _looks_like_namedb(s.get("definition", "")):
            s["definition"] = ""     # don't show name-db junk as a definition
        s.pop("addr", None)
        ded.append(s)
    gs = _glossary_sense(w)          # authoritative gnostic sense shown first
    if gs:
        senses = [gs] + senses
    # a plural with no real definition of its own (empty, or only a 'plural of X' stub)
    # borrows its singular's actual definition
    if _fb and (not senses or all(_is_stub(s.get("gloss", "")) for s in senses)):
        senses = senses + _fallback_senses(w)
    return {"found": True, "word": w, "address24": addr, "originals": originals,
            "strongs": ded, "senses": senses}


def word_lookup_ctx(w, book=None, ch=None, verse=None):
    """Context-aware word study: resolve a clicked English word to the ACTUAL original used in
    THIS verse, from the verse's own interlinear alignment (Isaiah 13:1 'burden' -> H4853 massa',
    not an unrelated English->Hebrew guess). Only when the verse has no matching token does it fall
    back to the generic lemma lookup -- so the panel shows the real word, and transliterates ONLY
    when there genuinely is no original to show."""
    wl = (w or "").lower().strip()
    if book and ch and verse:
        try:
            il = interlinear(book, int(ch), int(verse))
        except Exception:
            il = {"tokens": []}

        def _n(x):
            return re.sub(r"[^a-z]", "", (x or "").lower())

        tw = _n(wl)
        best = None
        if tw:
            for t in il.get("tokens", []):
                en = _n(t.get("en"))
                kjv = set(_n(x) for x in (t.get("kjv") or "").split())
                if en == tw or tw in kjv or (en and en.rstrip("s") == tw.rstrip("s") and abs(len(en) - len(tw)) <= 1):
                    best = t
                    break
        if best and best.get("strongs"):
            sidnum = best["strongs"]
            glyph = _ng(best.get("original") or best.get("lemma") or "")
            lang = LANG_NAME.get(_norm_lang(best.get("lang")), best.get("lang") or "Hebrew")
            det = strongs_detail(sidnum)
            defn = det.get("definition") or best.get("gloss") or _ext_def(sidnum)
            # ONLY the original's own Strong's definition -- never the modern English-word senses
            # (which would drag in 'burden = toxins in an organism / a blast-furnace charge').
            senses = [{"pos": det.get("pos", ""), "gloss": defn, "lang": lang}] if defn else []
            return {"found": True, "word": w, "address24": None, "fromVerse": True,
                    "originals": [{"glyph": glyph, "sid": best.get("sid"), "id": sidnum, "language": lang}],
                    "strongs": [{"id": sidnum, "language": lang, "pos": det.get("pos", ""),
                                 "definition": defn, "glyph": glyph, "sid": best.get("sid")}],
                    "senses": senses}
    r = word_lookup(wl)
    if r.get("found") and (r.get("strongs") or r.get("originals") or r.get("senses")):
        return r
    e = english_def(wl)
    return e if e.get("found") else r


def english_def(word):
    """Offline English dictionary (WordNet): defines ANY plain English word -- the 'smallest
    responding' definitions layer, with no lexicon and no model needed."""
    w = (word or "").lower().strip()
    if not w:
        return {"found": False}
    c = _c(ENGLISH_DB)
    row = c.execute("SELECT defs FROM english WHERE word=?", (w,)).fetchone()
    if not row:
        alts = []
        if w.endswith("ies"):
            alts.append(w[:-3] + "y")
        if w.endswith("es"):
            alts.append(w[:-2])
        if w.endswith("s"):
            alts.append(w[:-1])
        for a in alts:
            row = c.execute("SELECT defs FROM english WHERE word=?", (a,)).fetchone()
            if row:
                break
    if not row:
        return {"found": False, "word": word}
    try:
        items = json.loads(row[0])
    except Exception:
        items = []
    senses = [{"pos": it.get("pos", ""), "gloss": it.get("def", ""), "lang": "English"} for it in items]
    return {"found": True, "word": word, "english": True, "originals": [], "strongs": [], "senses": senses}


def strongs_detail(sid):
    """Full Strong's entry (for the clickable Strong's -> center investigation)."""
    c = _c(LEX)
    src = "makor:strong:" + sid if not sid.startswith("makor:") else sid
    try:
        row = c.execute("SELECT source_id,language,source_record FROM lexical_nodes WHERE"
                        " source_id=?", (src,)).fetchone()
    except sqlite3.OperationalError:
        row = None   # lexicon absent: the openscriptures Strong's json answers below
    if not row:                       # no local node -> use openscriptures Strong's
        ext = _ext(sid)
        if ext:
            return {"found": True, "id": sid, "language": "Hebrew" if sid[:1].upper() == "H" else "Greek",
                    "lemma": ext.get("lemma", ""), "translit": ext.get("x", ""),
                    "pos": "", "pronounce": ext.get("p", ""),
                    "definition": _clean_markup(ext.get("def") or ext.get("kjv", "")), "derivation": ""}
        return {"found": False, "id": sid}
    j = {}
    try:
        j = json.loads(row[2]) if row[2] and row[2].strip().startswith("{") else {}
    except Exception:
        j = {}
    gloss, pos = _gloss_from(row[2])
    sid_num = row[0].split(":")[-1]
    ext = _ext(sid_num)
    return {"found": True, "id": sid_num,
            "language": LANG_NAME.get(_norm_lang(row[1]), row[1] or "?"),
            "lemma": j.get("lemma") or ext.get("lemma", ""),
            "translit": j.get("translit") or j.get("xlit") or ext.get("x", ""),
            "pos": pos or j.get("part_of_speech", ""),
            "pronounce": j.get("pronounce") or ext.get("p", ""),
            "definition": _clean_markup(gloss or ext.get("def") or ext.get("kjv", "")),
            "derivation": _clean_markup(j.get("derivation", ""))}


def _first_words(text, n=5):
    return " ".join((text or "").replace("<BR>", " ").split()[:n])


def _ng(g):
    """Clean a displayed original glyph: drop the STEPBible morpheme separator '/',
    stray slashes/pipes, and Hebrew joining/verse punctuation (maqaf, sof-pasuq)."""
    if not g:
        return g
    for ch in ("/", "\\", "|", "־", "׀", "׃"):
        g = g.replace(ch, "")
    return g.strip()


# STEPBible book codes in canonical order (paired to Watchman's book_order below,
# so EVERY book -- not just KJV's few -- resolves its Hebrew/Greek interlinear).
STEP_CODES = ["Gen", "Exo", "Lev", "Num", "Deu", "Jos", "Jdg", "Rut", "1Sa", "2Sa",
              "1Ki", "2Ki", "1Ch", "2Ch", "Ezr", "Neh", "Est", "Job", "Psa", "Pro",
              "Ecc", "Sng", "Isa", "Jer", "Lam", "Ezk", "Dan", "Hos", "Jol", "Amo",
              "Oba", "Jon", "Mic", "Nam", "Hab", "Zep", "Hag", "Zec", "Mal", "Mat",
              "Mrk", "Luk", "Jhn", "Act", "Rom", "1Co", "2Co", "Gal", "Eph", "Php",
              "Col", "1Th", "2Th", "1Ti", "2Ti", "Tit", "Phm", "Heb", "Jas", "1Pe",
              "2Pe", "1Jn", "2Jn", "3Jn", "Jud", "Rev"]
_ABBR = None


def _abbr_map():
    global _ABBR
    if _ABBR is None:
        try:
            names = books()
            _ABBR = {n: STEP_CODES[i] for i, n in enumerate(names) if i < len(STEP_CODES)}
        except Exception:
            _ABBR = {}
    return _ABBR


# Paleo/ancient-Hebrew letter meanings (name + pictographic sense), for the
# letter-by-letter breakdown of a Hebrew word (read right-to-left).
HEB_LETTERS = {
    "א": ("Aleph", "ox — strength, leader, the first, God"),
    "ב": ("Bet", "house — household, family, in, within"),
    "ג": ("Gimel", "camel — to lift up, pride, to walk, benefit"),
    "ד": ("Dalet", "door — pathway, to enter, to move, hang"),
    "ה": ("He", "behold! — window, to reveal, breath, the"),
    "ו": ("Vav", "nail/hook — and, to add, to secure, connect"),
    "ז": ("Zayin", "weapon — to cut, sword, nourishment, harvest"),
    "ח": ("Chet", "wall/fence — to separate, protect, private, inner room"),
    "ט": ("Tet", "basket — to surround, contain, mud, to twist"),
    "י": ("Yod", "hand/arm — deed, work, to make, worship"),
    "כ": ("Kaf", "open palm — to cover, to allow, to bend, to tame"),
    "ל": ("Lamed", "shepherd's staff — to teach, to lead, authority, toward"),
    "מ": ("Mem", "water — chaos, mighty, blood, nations, from"),
    "נ": ("Nun", "seed/fish — life, activity, continuation, heir, offspring"),
    "ס": ("Samekh", "prop/support — to lean, to uphold, to twist, protect"),
    "ע": ("Ayin", "eye — to see, to know, to experience, to watch, fountain"),
    "פ": ("Pe", "mouth — to speak, word, to open, to blow, edge"),
    "צ": ("Tsade", "fish-hook — to catch, need, desire, the righteous, to pull"),
    "ק": ("Qof", "back of the head / horizon — behind, the least, to circle, time, holiness"),
    "ר": ("Resh", "head — person, the first/top, beginning, chief"),
    "ש": ("Shin", "teeth — to consume, to destroy, sharp, two, to press, Almighty"),
    "ת": ("Tav", "mark/sign — signature, covenant, monument, to seal, the end/completion"),
}
_FINALS = {"ך": "כ", "ם": "מ", "ן": "נ",
           "ף": "פ", "ץ": "צ"}
# rough phonetic value of each Hebrew letter (for the pronunciation guide)
HEB_SOUND = {"א": "ʼ", "ב": "b", "ג": "g", "ד": "d", "ה": "h", "ו": "v", "ז": "z",
             "ח": "kh", "ט": "t", "י": "y", "כ": "k", "ל": "l", "מ": "m", "נ": "n",
             "ס": "s", "ע": "ʽ", "פ": "p", "צ": "ts", "ק": "q", "ר": "r", "ש": "sh",
             "ת": "t"}
# Greek -> Latin romanization (accents stripped first)
GRK_SOUND = {"α": "a", "β": "b", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "e",
             "θ": "th", "ι": "i", "κ": "k", "λ": "l", "μ": "m", "ν": "n", "ξ": "x",
             "ο": "o", "π": "p", "ρ": "r", "σ": "s", "ς": "s", "τ": "t", "υ": "u",
             "φ": "ph", "χ": "ch", "ψ": "ps", "ω": "o"}
_CODE2BOOK = None


# Hebrew niqqud (vowel points) -> sound, for a VOCALIZED transliteration.
_VOWELS = {"ְ": "e", "ֱ": "e", "ֲ": "a", "ֳ": "o", "ִ": "i",
           "ֵ": "e", "ֶ": "e", "ַ": "a", "ָ": "a", "ֹ": "o",
           "ֺ": "o", "ֻ": "u", "ׇ": "o"}
_DAGESH, _SHIN_DOT, _SIN_DOT = "ּ", "ׁ", "ׂ"


def _heb_groups(word):
    """Split a pointed Hebrew word into [(base_letter, original_char, [marks]), ...]
    -- each consonant with the vowel points that follow it."""
    groups = []
    for ch in (word or ""):
        cc = ord(ch)
        base = _FINALS.get(ch, ch)
        if base in HEB_LETTERS:
            groups.append([base, ch, []])
        elif 0x0591 <= cc <= 0x05C7 and groups:
            groups[-1][2].append(ch)
    return groups


_HEB_CONS = {"ג": "g", "ד": "d", "ה": "h", "ז": "z", "ח": "kh",
             "ט": "t", "י": "y", "ל": "l", "מ": "m", "נ": "n",
             "ס": "s", "צ": "ts", "ק": "q", "ר": "r", "ת": "t"}


def _consonant_sound(base, marks):
    dagesh = _DAGESH in marks
    if base == "ב":  # bet
        return "b" if dagesh else "v"
    if base == "כ":  # kaf
        return "k" if dagesh else "kh"
    if base == "פ":  # pe
        return "p" if dagesh else "f"
    if base == "ש":  # shin/sin
        return "s" if _SIN_DOT in marks else "sh"
    if base in ("א", "ע"):  # aleph, ayin -> glottal, silent in the guide
        return ""
    if base == "ו":  # vav: shuruq -> u, holam male -> o, else consonant v
        if dagesh and not any(m in _VOWELS for m in marks):
            return "u"
        if "ֹ" in marks or "ֺ" in marks:
            return "o"
        return "v"
    return _HEB_CONS.get(base, "")


def _syllable(base, marks, idx):
    cs = _consonant_sound(base, marks)
    vowels = "".join(_VOWELS[m] for m in marks if m in _VOWELS)
    if base == "ו" and cs in ("o", "u"):
        vowels = ""                         # vav already encodes its vowel
    if base == "י" and not vowels and idx > 0:
        cs = ""                             # mater lectionis (silent yod)
    return cs + vowels


def translit_hebrew(word):
    groups = _heb_groups(word)
    syl = [_syllable(b, m, i) for i, (b, _o, m) in enumerate(groups)]
    return "".join(syl), syl, groups


def _greek_translit(word):
    import unicodedata
    out, rough, seen_vowel = [], False, False
    for ch in unicodedata.normalize("NFD", word or ""):
        cc = ord(ch)
        if cc == 0x0314:
            rough = True; continue          # rough breathing -> h
        if 0x0300 <= cc <= 0x036F:
            continue                        # drop smooth breathing + accents
        low = ch.lower()
        if low in GRK_SOUND:
            if rough and not seen_vowel and low in "αεηιουω":
                out.append("h"); rough = False
            out.append(GRK_SOUND[low])
            if low in "αεηιουω":
                seen_vowel = True
    return "".join(out)


def romanize(word):
    """VOCALIZED transliteration: reads Hebrew niqqud (vowel points) for a real
    pronunciation, and Greek accents/breathing for Greek -- not just consonants."""
    full, _syl, groups = translit_hebrew(word)
    if groups:
        return full
    return _greek_translit(word)


_GRK_REV = None


def _greek_for_word(w):
    """Reverse index English KJV word -> the Greek lemma (glyph) that Strong's renders
    it from, so a word study can show its Greek even when no Greek glyph was passed.
    Prefers the entry whose rendering list is shortest (most specific to this word)."""
    global _GRK_REV
    if _GRK_REV is None:
        _GRK_REV = {}
        try:
            with open(_STRONGS_EXT_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        best_len = {}
        for key, e in data.items():
            if not key.startswith("G"):
                continue
            lemma = (e.get("lemma") or "").strip()
            if not lemma:
                continue
            renders = re.findall(r"[A-Za-z]+", e.get("kjv", "") or "")
            n = len(renders) or 99
            for r in renders:
                rl = r.lower()
                if len(rl) < 2:
                    continue
                if rl not in best_len or n < best_len[rl]:
                    best_len[rl] = n
                    _GRK_REV[rl] = lemma
    if not w:
        return ""
    if w in _GRK_REV:
        return _GRK_REV[w]
    # try a light singularisation so a plural still resolves
    for cand in (w[:-1], w[:-2], w[:-3] + "y" if w.endswith("ies") else ""):
        if cand and cand in _GRK_REV:
            return _GRK_REV[cand]
    return ""


def _code2book():
    global _CODE2BOOK
    if _CODE2BOOK is None:
        try:
            names = books()
            _CODE2BOOK = {STEP_CODES[i]: n for i, n in enumerate(names) if i < len(STEP_CODES)}
        except Exception:
            _CODE2BOOK = {}
    return _CODE2BOOK


def _parse_step_ref(sid):
    """'step:Jhn.3.16#05=G...' -> ('John', 3, 16) or None."""
    if not sid or not sid.startswith("step:"):
        return None
    core = sid[5:].split("#", 1)[0]
    parts = core.split(".")
    if len(parts) < 3:
        return None
    book = _code2book().get(parts[0], parts[0])
    try:
        return book, int(parts[1]), int(parts[2])
    except ValueError:
        return None


def hebrew_letters(word):
    """Letter-by-letter breakdown of a Hebrew word, in reading order (right-to-left).
    Each letter carries its base sound AND its vocalized syllable (consonant+vowel)."""
    _full, syl, groups = translit_hebrew(word)
    out = []
    for (base, orig, marks), s in zip(groups, syl):
        nm, mn = HEB_LETTERS[base]
        out.append({"letter": orig, "name": nm, "meaning": mn,
                    "sound": HEB_SOUND.get(base, ""), "syllable": s,
                    "final": orig in _FINALS})
    return out


def deepstudy(sid):
    """Deep study of a clicked original token: definition + Strong's + cited
    use-cases across scripture + (for Hebrew) a paleo letter breakdown."""
    c = _c(LEX)
    try:
        row = c.execute("SELECT address24,canonical_lemma,language,source_record FROM"
                        " lexical_nodes WHERE source_id=?", (sid,)).fetchone()
    except sqlite3.OperationalError:
        row = None
    if not row:
        return {"found": False}
    addr, lemma, lang, rec = row
    nl = _norm_lang(lang)
    strong, uses = None, []
    try:
        st = c.execute("SELECT target_address24 FROM lexical_routes WHERE source_address24=?"
                       " AND relation_type='strongs' LIMIT 1", (addr,)).fetchone()
    except sqlite3.OperationalError:
        st = None
    if st:
        saddr = st[0]
        sr = c.execute("SELECT source_id,canonical_lemma,language,source_record FROM"
                       " lexical_nodes WHERE address24=?", (saddr,)).fetchone()
        if sr:
            j = {}
            try:
                j = json.loads(sr[3]) if sr[3] and sr[3].strip().startswith("{") else {}
            except Exception:
                j = {}
            g, pos = _gloss_from(sr[3])
            snum = sr[0].split(":")[-1]; ext = _ext(snum)
            strong = {"id": snum, "en": sr[1] or "",
                      "language": LANG_NAME.get(_norm_lang(sr[2]), sr[2] or "?"),
                      "translit": j.get("translit") or j.get("xlit") or ext.get("x", ""),
                      "pronounce": j.get("pronounce") or j.get("pron") or ext.get("p", ""),
                      "pos": pos or j.get("part_of_speech", ""),
                      "definition": g or ext.get("def") or ext.get("kjv", "")}
            # cited use-cases: other tokens that route to this same Strong's entry
            seen = set()
            try:
                for (src_addr,) in c.execute("SELECT source_address24 FROM lexical_routes"
                        " WHERE target_address24=? AND relation_type='strongs' LIMIT 400", (saddr,)):
                    nd = c.execute("SELECT source_id FROM lexical_nodes WHERE address24=?",
                                   (src_addr,)).fetchone()
                    if not nd:
                        continue
                    ref = _parse_step_ref(nd[0])
                    if ref and ref not in seen:
                        seen.add(ref)
                        uses.append({"ref": "%s %d:%d" % ref, "book": ref[0],
                                     "chapter": ref[1], "verse": ref[2]})
                    if len(uses) >= 60:
                        break
            except sqlite3.OperationalError:
                pass
    letters = hebrew_letters(lemma)   # extract Hebrew consonants from the word itself
    pron = ((strong or {}).get("pronounce") or (strong or {}).get("translit") or romanize(lemma))
    return {"found": True, "word": _ng(lemma), "language": LANG_NAME.get(nl, lang),
            "strongs": strong, "uses": uses, "letters": letters,
            "pronounce": pron, "is_hebrew": bool(letters)}


def usecases(sid="", strong=""):
    """Cited use-cases (verses that route to the same Strong's entry) for the new 2-column
    deep-dive. By token `sid` (reuses deepstudy) OR by a Strong's number/id `strong`."""
    if sid:
        d = deepstudy(sid)
        return {"uses": d.get("uses", [])}
    if not strong:
        return {"uses": []}
    c = _c(LEX)
    if c is None:
        return {"uses": []}
    sidkey = strong if strong.startswith("makor:strong:") else ("makor:strong:" + strong.lstrip(":"))
    try:
        row = c.execute("SELECT address24 FROM lexical_nodes WHERE source_id=?", (sidkey,)).fetchone()
    except sqlite3.OperationalError:
        row = None
    if not row:
        return {"uses": []}
    saddr = row[0]; uses = []; seen = set()
    try:
        for (src_addr,) in c.execute("SELECT source_address24 FROM lexical_routes"
                " WHERE target_address24=? AND relation_type='strongs' LIMIT 400", (saddr,)):
            nd = c.execute("SELECT source_id FROM lexical_nodes WHERE address24=?", (src_addr,)).fetchone()
            if not nd:
                continue
            ref = _parse_step_ref(nd[0])
            if ref and ref not in seen:
                seen.add(ref)
                uses.append({"ref": "%s %d:%d" % ref, "book": ref[0], "chapter": ref[1], "verse": ref[2]})
            if len(uses) >= 60:
                break
    except sqlite3.OperationalError:
        pass
    return {"uses": uses}


def chapter_study(book, ch):
    """The book's Hebrew name + meaning + paleo letter breakdown (for selecting the
    chapter/book itself)."""
    e = BOOK_HEBREW.get(book)
    if not e:
        return {"found": False, "book": book, "chapter": ch}
    heb, tr, mean = e
    return {"found": True, "book": book, "chapter": ch, "hebrew": heb,
            "translit": tr, "meaning": mean, "letters": hebrew_letters(heb)}


# function/stopwords that occur in nearly every verse -- never let one of these be
# chosen as a content token's "rendering used here" (it would mislabel a real word).
_KJV_STOP = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at", "by",
    "for", "with", "from", "as", "that", "this", "these", "those", "it", "is",
    "was", "be", "are", "were", "have", "had", "has", "not", "so", "then",
    "which", "who", "whom", "unto", "up", "out", "into", "upon", "shall", "will",
    "his", "her", "their", "them", "he", "she", "they", "him", "we", "ye", "you",
    "i", "my", "thy", "thou", "thee", "your", "our", "all", "if", "when", "how",
    "there", "here", "also", "now", "even", "s",
}


def _kjv_forms(raw):
    """The KJV rendering words for a Strong's entry, INCLUDING the forms Strong's
    writes with hyphen-parentheses -- 'inhabit(-ant)'->inhabitant, 'hear(-ken)'->hearken,
    '(him-, my-)self'->himself/myself. Without this those renderings split into pieces
    ('inhabit'+'ant') and a real translation is wrongly flagged 'supplied'."""
    if not raw:
        return []
    words = re.findall(r"[A-Za-z]+", raw)
    # base immediately followed by a "(-suffix...)" -> base+firstsuffix
    for base, suf in re.findall(r"([A-Za-z]{2,})\(-?([A-Za-z]{2,10})", raw):
        words.append(base + suf)
    # "(pre-, pre-)base" -> each prefix + base
    for pres, base in re.findall(r"\(((?:[A-Za-z]+-[,\s]*){1,6})\)([A-Za-z]{2,})", raw):
        for pre in re.findall(r"([A-Za-z]+)-", pres):
            words.append(pre + base)
    return words


_STRONG_OV = None


def _strong_overrides():
    global _STRONG_OV
    if _STRONG_OV is None:
        import unicodedata
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "taviel_strong_overrides.json"), encoding="utf-8") as f:
                _STRONG_OV = {unicodedata.normalize("NFC", k): v
                              for k, v in json.load(f).items() if not k.startswith("_")}
        except Exception:
            _STRONG_OV = {}
    return _STRONG_OV


def _glyph_bare(lemma):
    """The bare original glyph from a lemma like 'ἤρξατο (ērxato)' -> 'ἤρξατο', NFC-normalised
    so it matches the override keys regardless of accent-composition form."""
    import unicodedata
    return unicodedata.normalize("NFC", re.split(r"\s*\(", (lemma or "").strip(), 1)[0].strip())


def interlinear(book, ch, verse):
    c = _c(LEX)
    # the KJV verse's own words -- so each token shows the rendering actually used HERE
    # (echad -> "one", not the alphabetical-first "a"; H2275 -> "Hebron", not "Chebron").
    verse_words = set()
    try:
        wc = _c(WATCHMAN)
        wr = wc.execute("SELECT text FROM verses WHERE book=? AND chapter=? AND verse=?",
                        (book, ch, verse)).fetchone()
        if wr and wr[0]:
            verse_words = set(w.lower() for w in re.findall(r"[A-Za-z]+", wr[0]))
    except Exception:
        pass
    abbr = _abbr_map().get(book, book[:3])
    lo = "step:%s.%d.%d#" % (abbr, ch, verse)
    hi = "step:%s.%d.%d$" % (abbr, ch, verse)
    try:
        rows = c.execute("SELECT address24,source_id,canonical_lemma,language FROM lexical_nodes"
                         " WHERE source_id>=? AND source_id<? ORDER BY source_id LIMIT 60",
                         (lo, hi)).fetchall()
    except sqlite3.OperationalError:
        rows = []
    toks = []
    for addr, sid, lemma, lang in rows:
        gloss, sid_num, en = "", "", ""
        try:
            # a word may route to a grammatical prefix (H9xxx) AND its content root;
            # prefer the CONTENT root so "the assembly" resolves to H5712, not "the".
            routes = c.execute("SELECT target_address24 FROM lexical_routes WHERE"
                               " source_address24=? AND relation_type='strongs' LIMIT 8", (addr,)).fetchall()
            best, best_content = None, False
            for (taddr,) in routes:
                sr = c.execute("SELECT source_id,canonical_lemma,source_record FROM lexical_nodes"
                               " WHERE address24=?", (taddr,)).fetchone()
                if not sr:
                    continue
                sn = sr[0].split(":")[-1]
                content = not re.match(r"^[HG]9\d{3}$", sn)   # H9xxx = grammatical prefix
                if best is None or (content and not best_content):
                    best, best_content = sr, content
                if content:
                    break
            if best:
                sid_num = best[0].split(":")[-1]
                en = best[1] or ""
                g, _ = _gloss_from(best[2])
                gloss = _first_words(g, 6)
                if not en or re.match(r"^[HG]?\d+$", en.strip(), re.I):
                    en = _first_words(re.sub(r"^[\s\d)\.\-]+", "", g or ""), 4)
                if not en:      # last resort: openscriptures Strong's definition
                    en = _first_words(re.sub(r"^[\s\d)\.\-]+", "", _ext(sid_num).get("def", "")), 4)
                if not gloss:
                    gloss = _ext_def(sid_num)
        except sqlite3.OperationalError:
            pass
        # CORRECTION LAYER: a few words are mis-tagged to the wrong Strong's in the source
        # interlinear (began -> G0757 'rule' not G0756 'begin'; greater -> G3173 not G3187).
        # Fix by the original glyph so the kjv rendering list -- and the highlight classifier --
        # use the right entry. Documented corrections in taviel_strong_overrides.json, not a paper-over.
        _ov = _strong_overrides().get(_glyph_bare(lemma))
        if _ov:
            sid_num = _ov.get("sid", sid_num)
            en = _ov.get("en") or en
            gloss = _ext_def(sid_num) or gloss
        # the actual KJV rendering (e.g. H2275 -> "Hebron") so the token links to the KJV word,
        # instead of the lexicon's transliteration lemma ("Chebron, a place in"). This is what
        # makes hovering the English light its Hebrew/Greek original.
        kjv_words = _kjv_forms(_ext(sid_num).get("kjv", "")) if sid_num else []
        # prefer the KJV rendering that appears in THIS verse -- but NEVER a function/stopword
        # ('the','in','of'...), and ONLY when it is UNAMBIGUOUS (exactly one distinct
        # rendering present). A shared lemma's idiom fragment ("God" from ginomai's
        # "God forbid") or a sibling token's word must not hijack the gloss; keep the
        # clean lemma gloss when the choice is ambiguous.
        cand = [w for w in kjv_words
                if w.lower() in verse_words and w.lower() not in _KJV_STOP]
        if cand and len({w.lower() for w in cand}) == 1:
            en = cand[0]
        toks.append({"original": _ng(lemma), "lemma": _ng(lemma), "lang": lang, "sid": sid,
                     "strongs": sid_num, "gloss": gloss, "en": en,
                     # the FULL KJV rendering list (not truncated) is the authoritative
                     # set of English words the KJV uses for this original -- it drives
                     # word-recognition, so a translated word is not falsely 'supplied'.
                     "kjv": " ".join([w for w in kjv_words if len(w) > 1][:100])})
    return {"tokens": toks}


def original_def(sid):
    """Define a clicked Hebrew/Greek interlinear token: follow its Strong's route."""
    c = _c(LEX)
    try:
        row = c.execute("SELECT address24,canonical_lemma,language,source_record FROM"
                        " lexical_nodes WHERE source_id=?", (sid,)).fetchone()
    except sqlite3.OperationalError:
        row = None
    if not row:
        return {"found": False}
    addr, lemma, lang, rec = row
    strongs = None
    st = c.execute("SELECT target_address24 FROM lexical_routes WHERE source_address24=?"
                   " AND relation_type='strongs' LIMIT 1", (addr,)).fetchone()
    if st:
        sr = c.execute("SELECT source_id,language,source_record FROM lexical_nodes WHERE"
                       " address24=?", (st[0],)).fetchone()
        if sr:
            gloss, pos = _gloss_from(sr[2])
            strongs = {"id": sr[0].split(":")[-1],
                       "language": LANG_NAME.get(_norm_lang(sr[1]), sr[1] or "?"),
                       "pos": pos, "definition": gloss or ""}
    gloss, pos = _gloss_from(rec)
    return {"found": True, "original": lemma, "lang": LANG_NAME.get(_norm_lang(lang), lang),
            "strongs": ([strongs] if strongs else []),
            "senses": ([{"gloss": gloss, "pos": pos, "lang": "original"}] if gloss else [])}


# ---- apocrypha reading (Book -> Chapter -> Verse, whole works) ----------------
_FRONTMATTER = ("introduction", "front matter", "contents", "acknowledg", "bibliograph",
                "preface", "foreword", "index", "abbreviation", "copyright", "shambhala",
                "glossary", "appendix", "editor", "publisher", "table of", "about the",
                "dedication", "colophon", "series", "translated by", "translation of")


def _is_frontmatter(name):
    n = (name or "").lower().strip()
    if any(k in n for k in _FRONTMATTER):
        return True
    return n in ("part one", "part two", "part three", "part four", "part five",
                 "part six", "part seven", "part eight", "unknown", "bible")


def _corpus_books(cid):
    d = _c(CORPUS_DB)
    if d is None:
        return []
    out = []
    try:
        for bk in d.execute("SELECT book, GROUP_CONCAT(DISTINCT chapter) FROM corpus_units"
                            " WHERE corpus=? GROUP BY book ORDER BY MIN(ordinal)", (cid,)):
            chs = sorted({int(x) for x in (bk[1] or "").split(",") if x != ""})
            out.append({"book": bk[0], "chapters": chs or [1]})
    except sqlite3.OperationalError:
        return []   # schema mid-rewrite (chapter/verse columns being added)
    return out


def apoc_books(aid):
    """Left-panel index: the books (+ their chapters) inside an apocrypha work."""
    if aid.startswith("corpus:"):
        cid = aid.split(":", 1)[1]; bks = _corpus_books(cid)
        if cid != "yahweh_tsidkenu_full":     # keep intros only in Yahweh Tsidkenu
            bks = [b for b in bks if not _is_frontmatter(b["book"])]
        if cid in PROSE_CORPORA:
            for b in bks:
                b["chapters"] = [1]     # whole book reads at once (prose)
        return {"title": CORPUS_TITLES.get(cid, cid), "books": bks,
                "prose": cid in PROSE_CORPORA}
    if aid.startswith("enoch"):
        n = aid[-1]; c = _c(ENOCH)
        book = {"1": "1 Enoch", "2": "2 Enoch", "3": "3 Enoch"}[n]
        if c is None:
            return {"title": book, "books": []}
        rows = c.execute("SELECT DISTINCT chapter FROM verses WHERE book LIKE ?",
                         (book + "%",)).fetchall()
        if not rows:
            rows = c.execute("SELECT DISTINCT chapter FROM verses").fetchall()
        chs = sorted({int(r[0]) for r in rows if str(r[0]).strip().lstrip('-').isdigit()})
        return {"title": book, "books": [{"book": book, "chapters": chs}]}
    if aid == "gnostic_book":
        c = _c(YT)
        parts = c.execute("SELECT DISTINCT part, part_title FROM gnosis_book ORDER BY part").fetchall()
        return {"title": "Gnosis: The Eternal Mirror",
                "books": [{"book": "%d. %s" % (p[0], p[1]),
                           "chapters": [r[0] for r in c.execute(
                               "SELECT section FROM gnosis_book WHERE part=? ORDER BY section", (p[0],))]}
                          for p in parts]}
    if aid == "yahweh_tsidkenu":
        return {"title": "Yahweh Tsidkenu -- the Nine Keys", "books": [{"book": "The Nine Keys", "chapters": [1]}]}
    return {"title": aid, "books": []}


def _debalance_parens(t):
    """Drop stray UNMATCHED parentheses (OCR artifacts like '<great)') while keeping
    balanced pairs such as the '(1)' saying markers."""
    out, depth = [], 0
    for ch in t:
        if ch == "(":
            depth += 1
            out.append(ch)
        elif ch == ")":
            if depth > 0:
                depth -= 1
                out.append(ch)
            # else: stray close paren -> drop
        else:
            out.append(ch)
    if depth <= 0:
        return "".join(out)
    # still have unmatched '(' -> remove them via a reverse pass
    rev, d2 = [], 0
    for ch in reversed(out):
        if ch == ")":
            d2 += 1
            rev.append(ch)
        elif ch == "(":
            if d2 > 0:
                d2 -= 1
                rev.append(ch)
            # else: stray open paren -> drop
        else:
            rev.append(ch)
    return "".join(reversed(rev))


_WORDS = None


_COMMON = None


def _commonwords():
    """The COMMON English vocabulary (KJV verses + Strong's definition words) -- a
    much smaller, cleaner set than the 370k list. Used to decide whether a fragment
    is a genuine standalone word (which BLOCKS a merge, e.g. 'see'+'the') versus an
    OCR fragment (which allows one, e.g. 'estab'+'lished'). Built as a side effect of
    _wordset()."""
    if _COMMON is None:
        _wordset()
    return _COMMON


def _wordset():
    """A real-English dictionary (KJV vocabulary + Strong's + a 370k wordlist) used to
    VALIDATE that a rejoined OCR space-split is a genuine word. The parallel _COMMON set
    (KJV+Strong's only) decides whether a PART is a real word. Built once, cached."""
    global _WORDS, _COMMON
    if _WORDS is not None:
        return _WORDS
    import re
    common = set()
    try:
        c = sqlite3.connect(WATCHMAN, uri=True)
        for (t,) in c.execute("SELECT text FROM verses"):
            for w in re.findall(r"[a-z]+", (t or "").lower()):
                if len(w) >= 2:
                    common.add(w)
        c.close()
    except Exception:
        pass
    try:
        import json
        j = json.load(open(_res("taviel_strongs.json"), encoding="utf-8"))
        for e in (j.values() if isinstance(j, dict) else j):
            for fld in ("strongs_def", "kjv_def"):
                for w in re.findall(r"[a-z]+", str((e or {}).get(fld, "")).lower()):
                    if len(w) >= 2:
                        common.add(w)
    except Exception:
        pass
    s = set(common)
    try:   # comprehensive English wordlist (~370k) so 'con sort'->'consort', 'si multaneously'->'simultaneously'
        _wa = ("%s/Holorites_data/daeos/words_alpha.txt" % _YB).replace("/", os.sep)
        if not os.path.exists(_wa) and not os.environ.get("YAHBIBLE_NO_D"):
            _wa = r"D:\Holorites_data\daeos\words_alpha.txt"
        for w in open(_wa, encoding="utf-8"):
            w = w.strip().lower()
            if len(w) >= 2:
                s.add(w)
    except Exception:
        pass
    _COMMON = common
    _WORDS = s
    return s


_REJOIN_SUFFIX = {"ance", "ence", "ing", "tion", "sion", "ment", "ness", "nesses",
                  "ity", "ous", "ful", "able", "ible", "est", "ers", "er", "ed", "ly",
                  "al", "or", "ion", "ies", "ish", "dom", "ship", "ard", "ary", "ate",
                  "lished", "ished", "ings", "ments", "tions", "sions", "ances", "ences"}
# Longer bound prefixes -- when both parts look like words ('trans'+'formed') the split
# is still spurious. Short prefixes (pro, re, un, pre...) are handled by the length rule
# below; standalone words (over, under, out, with) are deliberately EXCLUDED so
# 'over'+'all' is never merged to 'overall'.
_MERGE_PREFIX = {"pro", "re", "un", "dis", "fore", "trans", "inter", "mis", "non",
                 "anti", "pre", "semi", "multi", "counter", "super", "ex", "en", "em"}


# Common short English words the KJV set may lack (KJV says 'hath' not 'has') -- these
# must count as genuine words so 'has'+'an' is never fused to 'hasan', 'go'+'down' to
# 'godown', etc. The 2-4 letter band is where the long-tail list has the most junk.
_COMMON_EXTRA = set((
    "has an as is it its his her him our you your are was were been did does don can "
    "will nor yet too also than then this that here there when who all any few own out "
    "off down over under such only more most into onto upon new old two one see god son "
    "day way let get got had end far big use law war art act age air man men us my me do "
    "no go up on at by to of or if he we they them she").split())


def _isword(x, W, C):
    """A fragment counts as a genuine standalone word (which BLOCKS an OCR merge) if it
    is in the COMMON vocabulary (KJV + Strong's), a common short function word, or is a
    length-5+ entry in the big 370k list. The length-5 floor separates real words like
    'human'/'stand' (block merging) from junk 2-4 letter long-tail entries like
    'te'/'trad'/'estab' (OCR fragments that allow a merge)."""
    return x in C or x in _COMMON_EXTRA or (len(x) >= 5 and x in W)


def _should_merge(al, bl, W):
    """Decide whether two space-separated fragments should be rejoined into one word.
    Merge only when the joined form is a real word AND at least one side is an OCR
    fragment (not a genuine word by _isword) OR a known bound prefix/suffix is present.
    So 'see'+'the'->seethe and 'over'+'all'->overall are LEFT ALONE, while 'estab'+
    'lished', 'Te'+'trad'->Tetrad, 'like'+'nesses', 'dwell'+'ing', 'pro'+'claim' rejoin."""
    if len(al) < 2 or len(bl) < 2 or (al + bl) not in W:
        return False
    C = _commonwords()
    a_frag = not _isword(al, W, C)
    b_frag = not _isword(bl, W, C)
    return a_frag or b_frag or bl in _REJOIN_SUFFIX or al in _MERGE_PREFIX


def _rejoin_once(t, W):
    import re
    toks = t.split(" ")
    out, i, n = [], 0, len(toks)
    while i < n:
        a = toks[i]
        if i + 1 < n and re.fullmatch(r"[A-Za-z]+", a):
            m = re.match(r"^([A-Za-z]+)([^A-Za-z].*)?$", toks[i + 1])
            if m:
                bw, tail = m.group(1), (m.group(2) or "")
                al, bl = a.lower(), bw.lower()
                # a lowercase word never fuses to a following Capitalised fragment --
                # 'the Te trad' must not become 'theTe'; the capital marks a new word,
                # so 'Te' is left to join 'trad' -> 'Tetrad' on the next step.
                case_boundary = a[-1].islower() and bw[0].isupper()
                if not case_boundary and _should_merge(al, bl, W):
                    out.append(a + bw + tail)
                    i += 2
                    continue
        out.append(a)
        i += 1
    return " ".join(out)


def _rejoin_across(verses):
    """Rejoin a word split ACROSS two adjacent verses (unit boundary): the tail word of
    one verse + the head word of the next forming a real word ('...ap' | 'peared...' ->
    '...appeared'). The joined word is kept on the first verse."""
    import re
    W = _wordset()
    if not W or len(verses) < 2:
        return verses
    for i in range(len(verses) - 1):
        a, b = verses[i]["text"], verses[i + 1]["text"]
        ma = re.search(r"([A-Za-z]+)\s*$", a)
        mb = re.match(r"^\s*([A-Za-z]+)", b)
        if not (ma and mb):
            continue
        aw, bw = ma.group(1), mb.group(1)
        al, bl = aw.lower(), bw.lower()
        if _should_merge(al, bl, W):
            verses[i]["text"] = a[:ma.start(1)] + aw + bw
            verses[i + 1]["text"] = b[mb.end(1):].lstrip()
    return [v for v in verses if v["text"]]


def _rejoin_splits(t):
    """Rejoin words the OCR split with a space ('de scended' -> 'descended',
    'ignor ance' -> 'ignorance'). Two passes catch chained splits ('de scend ed').
    Conservative: only when the merged token is a real dictionary word."""
    W = _wordset()
    if not W:
        return t
    prev = None
    for _ in range(3):
        t = _rejoin_once(t, W)
        if t == prev:
            break
        prev = t
    return t


def _clean_prose(t):
    """Strip scholarly manuscript apparatus from Nag Hammadi / Gnostic-Bible text:
    the ubiquitous line-break bars misread as '1', the 5/10/15... line numbers, page
    numbers, and digits fused into words ('that2 0' -> 'that'), plus bracket clutter --
    leaving readable prose. The source rows are never modified."""
    import re
    t = re.sub(r"\[\s*\.{2,}[^\]]*\]", " … ", t)   # [... n ...] lacunae -> ellipsis
    t = re.sub(r"\.{3,}", " … ", t)
    t = re.sub(r"[\[\]]", " ", t)                        # drop remaining brackets
    t = re.sub(r"[<>]", " ", t)                          # editorial insertion marks <he> -> keep text
    t = _debalance_parens(t)                             # strip stray unmatched parens ('<great)' -> 'great')
    # editorial grammar/apparatus markers that mean nothing to a reader: (sg.) (pl.)
    # (pi.=pl. OCR) (lit.) (Gr.) (Copt.) (sic) (cf.) (i.e.) (e.g.) ...
    t = re.sub(r"\(\s*(?:sg|pl|pi|lit|var|Gr|Grk|Heb|Aram|Copt|Coptic|sic|sc|cf|"
               r"i\.?e|e\.?g|marg|mss?|emend(?:ed)?|conj|om|add|masc|fem|neut|"
               r"pass|act|impf|aor|subj)\.?\s*\)", " ", t, flags=re.I)
    t = re.sub(r"\(\s*\?+\s*\)", " ", t)                 # '(?)' editorial-uncertainty marks
    t = re.sub(r"(?<!\S)\d{1,3}(?!\S)", " ", t)          # standalone line / page numbers
    t = re.sub(r"([A-Za-z]{2,})\d{1,3}\b", r"\1", t)     # digits fused to a word's end
    t = re.sub(r"\b\d{1,3}([A-Za-z]{2,})", r"\1", t)     # digits fused to a word's start
    t = re.sub(r"([.,;:!?”’\"'])\s?\d{1,3}(?=\s|$|[”’\"'])", r"\1", t)  # digits after punctuation/quote
    # OCR: a standalone capital 'T' is a mis-read 'I' ('T am a jealous God' -> 'I am...')
    t = re.sub(r"(?<![A-Za-z0-9.])T(?=[ ,;:!?’”\"'])", "I", t)
    # rejoin words split across a line-break hyphen: a short/suffix continuation is a
    # broken word (compil- ing -> compiling); a longer one is a real compound (keep '-')
    _suf = {"ing", "ed", "s", "es", "ly", "tion", "sion", "ness", "ment", "er", "ers",
            "ity", "al", "ous", "ful", "est", "en", "ance", "ence", "ted", "ded"}
    t = re.sub(r"([a-z])-\s+([a-z]+)",
               lambda m: m.group(1) + m.group(2) if (m.group(2) in _suf or len(m.group(2)) <= 3)
               else m.group(1) + "-" + m.group(2), t)
    t = re.sub(r"\s+([.,;:!?])", r"\1", t)               # tidy punctuation spacing
    t = re.sub(r"\s+…\s+", " … ", t)
    t = re.sub(r"\s{2,}", " ", t)
    t = _rejoin_splits(t.strip())                        # rejoin OCR space-splits
    return t.strip()


def _strip_intro(units):
    """Drop a leading SCHOLARLY INTRODUCTION (the essay 'The <Title> is a ...' that
    precedes the actual scripture in these anthologies), keeping the versified text.
    Conservative: only strips when a scripture incipit is found AND the leading block
    reads as scholarly commentary -- otherwise keeps everything, so no scripture is lost.
    `units` is a list of (chapter, verse, text)."""
    import re
    META = re.compile(
        r"\b(scholars?|manuscript|codex|copt|greek text|translat|centur|tractate|"
        r"treatise|nag hammadi|heresiolog|polemical|apocryph|is a |is the |"
        r"attributed to|the author|this (text|work|gospel|treatise)|composed|"
        r"scholarship|new testament|dialect|papyr|redact|the gospel of|version of)\b", re.I)
    START = re.compile(
        r"^\s*[“\"']?\(?\s*1\s*[\).]|^\s*These are (the|hidden|secret)|"
        r"^\s*[“\"'](?=[A-Z])|^\s*In the beginning|^\s*The (teaching|revelation|secret|book|"
        r"apocalypse|reality|thunder|word) of|^\s*It is I|^\s*I am (the|he|a )|"
        r"^\s*(Jesus|Yeshua|The Lord|The Savi)", re.I)
    n = len(units)
    start = None
    for i, (ch, v, t) in enumerate(units):
        if START.search((t or "").lstrip()[:60]):
            start = i
            break
    if start and 0 < start < n * 0.75:
        lead = " ".join((u[2] or "") for u in units[:start])
        if META.search(lead):
            return units[start:]
    return units


def _outro_apparatus(t):
    """True if a unit is trailing SCHOLARLY APPARATUS (analytical notes / footnotes /
    citations) rather than the text itself -- used to strip the outro."""
    import re
    t = t or ""
    # a unit with a clear SPEECH marker or saying-number is scripture, never apparatus
    if re.search(r"\b(said|saith|answered|spake|spoke|Amen|verily)\b|\(\s*\d+\s*\)", t, re.I):
        return False
    cit = re.search(r"\([A-Z][a-z]{1,6}\.[^)]{0,40}\d|\b\d+[,:]\d+\b|\bpp?\.\s*\d+", t)  # (Hyp. Arch. 95,5) / 108,2-31
    fnote = re.match(r"^\s*\d{1,3}\.\s+[A-Z“\"']", t)                 # '110. Or "enclosure"'
    meta = len(re.findall(
        r"\b(codex|codices|nag hammadi|recension|version|manuscript|scholars?|sethian|"
        r"demiurge|designated|ascribed|affinity|tractate|redact|dialect|coptic|greek text|"
        r"valentinian|barbeloite|scholarship|apparatus|parallel|attested|reconstruct|"
        r"editor|colophon|incipit|paucity|responsible for|is held|generally|presides|"
        r"the shorter version|the (?:text|treatise|author) of|insight into|its content)\b",
        t, re.I))
    return bool(cit) or bool(fnote) or meta >= 2


def _strip_outro(units):
    """Drop the trailing scholarly apparatus (afterword / notes / footnotes) that is not
    part of the original text. Robust to gaps: strips the longest trailing block that is
    MOSTLY apparatus (>=60%) and begins with an apparatus unit, keeping >=45% of the book."""
    n = len(units)
    app = [_outro_apparatus(u[2] or "") for u in units]
    cut, cnt = n, 0
    for i in range(n - 1, -1, -1):
        cnt += 1 if app[i] else 0
        total = n - i
        if app[i] and cnt >= total * 0.6 and i >= n * 0.45:
            cut = i
    return units[:cut] if cut < n else units


def _reversify(text):
    """Re-segment a continuous text into verses that begin at REAL boundaries (never
    mid-sentence): at the text's own '(N)' saying/section markers where present (their
    original numbering, kept inline), otherwise at sentence boundaries grouped to a
    readable size. Returns [{verse, text}] numbered sequentially."""
    import re
    text = re.sub(r"\s{2,}", " ", text or "").strip()
    if not text:
        return []
    markers = list(re.finditer(r"\(\s*\d+\s*\)", text))
    segs = []
    if len(markers) >= 3:
        bounds = sorted({0} | {m.start() for m in markers})
        for i, b in enumerate(bounds):
            e = bounds[i + 1] if i + 1 < len(bounds) else len(text)
            seg = text[b:e].strip()
            if seg:
                segs.append(seg)
    else:
        sents = re.split(r"(?<=[.!?”’\"'])\s+(?=[“”‘’\"'(]?[A-Z0-9])", text)
        cur = ""
        for s in sents:
            s = s.strip()
            if not s:
                continue
            if cur and len(cur) + len(s) + 1 > 300:
                segs.append(cur)
                cur = s
            else:
                cur = (cur + " " + s).strip()
        if cur:
            segs.append(cur)
    return [{"verse": i + 1, "text": s} for i, s in enumerate(segs)]


def _prose_paragraphs(text, target=480):
    """Group cleaned prose into readable paragraphs (~3-4 sentences) since the raw
    units carry no paragraph structure and split mid-sentence."""
    import re
    sents = re.split(r'(?<=[.!?])\s+(?=[A-Z"“…(])', text)
    paras, cur = [], ""
    for s in sents:
        s = s.strip()
        if not s:
            continue
        if cur and len(cur) + len(s) + 1 > target:
            paras.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        paras.append(cur)
    return paras


_MEQABYAN_BOOKS = {"I Meqabyan", "II Meqabyan", "III Meqabyan"}

# A brief POV/background shown at the head of each Enoch book (chapter 1), and notes marking
# where the seer's voice shifts from Enoch to Noah (the older "Book of Noah" fragments in 1 Enoch).
ENOCH_INTRO = {
    "1 Enoch": "1 Enoch (Ethiopic Enoch) is a composite of five books, preserved complete only "
    "in Ge'ez. Enoch is the speaker for most of it — recounting in the FIRST PERSON the visions "
    "and heavenly journeys shown to him before his translation, with the angel Uriel interpreting "
    "— and he sets it down as a testament for the far-off 'generation of the righteous' to come. "
    "Its five parts are the Book of the Watchers (1–36), the Book of Parables (37–71), the "
    "Astronomical Book (72–82), the Book of Dreams (83–90), and the Epistle of Enoch (91–108). "
    "Woven into it are older 'Book of Noah' fragments, where the seer's voice becomes Noah's — "
    "flagged where they occur.",
    "2 Enoch": "2 Enoch (Slavonic Enoch, 'The Book of the Secrets of Enoch') survives in Old "
    "Church Slavonic. Enoch narrates in the FIRST PERSON: two angels carry him up through the "
    "heavens, he is shown their contents and set before the Face of God, is written and instructed "
    "by the archangel Vrevoil, and is returned to earth for thirty days to deliver all he saw to "
    "his sons before his final ascent. Its close follows his line PAST him — Methuselah's "
    "priesthood and the wondrous birth of Melchizedek to Nir — rather than to Noah.",
    "3 Enoch": "3 Enoch (Hebrew, 'Sefer Hekhalot' — the Book of the Palaces) is a Merkabah-mystical "
    "work, and its narrator is NOT Enoch but Rabbi Ishmael, a sage of the 2nd century, who tells of "
    "his own ascent to the seventh heaven and the revelations given him there by the angel Metatron "
    "— the 'Prince of the Presence' and 'lesser YHWH,' who discloses that he is Enoch himself, taken "
    "up and transformed. So the point of view is Ishmael reporting the words of the exalted Enoch.",
}
ENOCH_NOAH = {
    ("1 Enoch", 60): "Here the voice shifts from Enoch to NOAH. This chapter is a surviving fragment "
    "of the older 'Book of Noah': the vision is dated by a life-year of the patriarch, and it is Noah "
    "— Enoch's great-grandson — who now beholds Behemoth and Leviathan and the storehouses of the "
    "elements.",
    ("1 Enoch", 65): "The voice is NOAH'S through chapters 65–68. Alarmed at the earth's coming "
    "destruction, Noah seeks out his great-grandfather Enoch at the ends of the earth and is shown "
    "the reason for the Flood and his own deliverance — a 'Book of Noah' section.",
    ("1 Enoch", 106): "The narration turns to NOAH'S BIRTH (chapters 106–107): Lamech is terrified at "
    "his radiant newborn son, Methuselah consults Enoch, and Enoch foretells that this child — Noah — "
    "will survive the coming Flood. Told ABOUT Noah rather than by Enoch.",
}


def apoc_verse(aid, book, ch, verse):
    """A single source verse in every version it has — original (Hebrew/Arabic/German), English,
    and (Torah) the KJV — for the right-panel verse study."""
    versions = []
    if not aid.startswith("corpus:"):
        return {"ref": "%s %d:%d" % (book, ch, verse), "versions": versions}
    cid = aid.split(":", 1)[1]; d = _c(CORPUS_DB)
    if d is None:
        return {"ref": "%s %d:%d" % (book, ch, verse), "versions": versions}
    try:
        r = d.execute("SELECT text FROM corpus_units WHERE corpus=? AND book=? AND chapter=? AND verse=?",
                      (cid, book, ch, verse)).fetchone()
        eng = r[0] if r else ""
        def _orig(table, extra):
            q = ("SELECT v.text FROM corpus_units cu LEFT JOIN %s v ON %s"
                 " WHERE cu.corpus=? AND cu.book=? AND cu.chapter=? AND cu.verse=?" % (table, extra))
            rr = d.execute(q, (cid, book, ch, verse)).fetchone()
            return rr[0] if rr and rr[0] else ""
        if cid in SEFARIA_CORPORA:
            t = _orig("sefaria_hebrew", "v.corpus=cu.corpus AND v.book=cu.book AND v.ordinal=cu.ordinal")
            if t: versions.append({"label": "Hebrew", "text": t})
        elif cid == "quran":
            t = _orig("quran_arabic", "v.book=cu.book AND v.ordinal=cu.ordinal")
            if t: versions.append({"label": "Arabic", "text": t})
        elif cid == "mandaean" and book in MAND_DE_BOOKS:
            t = _orig("mandaean_orig", "v.book=cu.book AND v.ordinal=cu.ordinal")
            if t: versions.append({"label": "German", "text": t})
        if eng:
            versions.append({"label": "English", "text": eng})
        if cid == "torah":
            wc = _c(WATCHMAN)
            if wc is not None:
                kr = wc.execute("SELECT text FROM verses WHERE book=? AND chapter=? AND verse=?",
                                (book, ch, verse)).fetchone()
                if kr: versions.append({"label": "KJV", "text": kr[0]})
    except sqlite3.OperationalError:
        pass
    return {"ref": "%s %d:%d" % (book, ch, verse), "versions": versions}


def apoc_chapter(aid, book, ch, variant="", compare=""):
    """One chapter of an apocrypha work as verses. `variant='std'` serves the standard-English
    normalization of the Meqabyan books; otherwise the verbatim (Iyaric) original.
    `compare='kjv'` (Torah only) pairs each verse with the KJV Old-Testament verse."""
    if aid.startswith("corpus:"):
        cid = aid.split(":", 1)[1]; d = _c(CORPUS_DB)
        # prose anthologies/books read continuously (no artificial verse markers);
        # only the Ethiopian Apocrypha carries real [1][2] verse structure.
        if cid in PROSE_CORPORA:
            rows = d.execute("SELECT chapter,verse,text FROM corpus_units WHERE corpus=?"
                             " AND book=? ORDER BY chapter,verse", (cid, book)).fetchall()
            if cid in CLEAN_CORPORA:
                # strip leading intro + trailing outro, then clean the WHOLE joined text
                # (fixes cross-unit word-splits) and RE-SEGMENT into verses that begin at
                # real boundaries -- the text's own '(N)' markers or sentence boundaries,
                # so a verse number never lands mid-sentence.
                units = _strip_outro(_strip_intro([(r[0], r[1], r[2]) for r in rows]))
                joined = _clean_prose(" ".join((u[2] or "") for u in units))
                return {"title": book, "cite": CORPUS_TITLES.get(cid, cid),
                        "prose": False, "verses": _reversify(joined)}
            return {"title": book, "cite": CORPUS_TITLES.get(cid, cid), "prose": True,
                    "verses": [{"verse": r[1], "text": r[2]} for r in rows]}
        is_meq = (cid == "ethiopian_apocrypha" and book in _MEQABYAN_BOOKS)
        is_quran = (cid == "quran")            # English default (corpus_units); 'orig' = Arabic
        is_sefaria = (cid in SEFARIA_CORPORA)  # English default; 'orig' = Hebrew (sefaria_hebrew)
        is_mand_de = (cid == "mandaean" and book in MAND_DE_BOOKS)  # English default; 'orig' = German
        has_variant = is_meq or is_quran or is_sefaria or is_mand_de
        vlabels = None
        if is_meq and variant == "std":
            rows = d.execute(
                "SELECT cu.verse, COALESCE(v.text, cu.text) FROM corpus_units cu"
                " LEFT JOIN meqabyan_std v ON v.book=cu.book AND v.ordinal=cu.ordinal"
                " WHERE cu.corpus=? AND cu.book=? AND cu.chapter=? ORDER BY cu.verse",
                (cid, book, ch)).fetchall()
            cur_variant = "std"
        elif is_quran and variant == "orig":
            rows = d.execute(
                "SELECT cu.verse, COALESCE(v.text, cu.text) FROM corpus_units cu"
                " LEFT JOIN quran_arabic v ON v.book=cu.book AND v.ordinal=cu.ordinal"
                " WHERE cu.corpus='quran' AND cu.book=? AND cu.chapter=? ORDER BY cu.verse",
                (book, ch)).fetchall()
            cur_variant = "orig"
        elif is_sefaria and variant == "orig":
            rows = d.execute(
                "SELECT cu.verse, COALESCE(v.text, cu.text) FROM corpus_units cu"
                " LEFT JOIN sefaria_hebrew v ON v.corpus=cu.corpus AND v.book=cu.book AND v.ordinal=cu.ordinal"
                " WHERE cu.corpus=? AND cu.book=? AND cu.chapter=? ORDER BY cu.verse",
                (cid, book, ch)).fetchall()
            cur_variant = "orig"
        elif is_mand_de and variant == "orig":
            rows = d.execute(
                "SELECT cu.verse, COALESCE(v.text, cu.text) FROM corpus_units cu"
                " LEFT JOIN mandaean_orig v ON v.book=cu.book AND v.ordinal=cu.ordinal"
                " WHERE cu.corpus='mandaean' AND cu.book=? AND cu.chapter=? ORDER BY cu.verse",
                (book, ch)).fetchall()
            cur_variant = "orig"
        else:
            rows = d.execute("SELECT verse,text FROM corpus_units WHERE corpus=? AND book=?"
                             " AND chapter=? ORDER BY verse", (cid, book, ch)).fetchall()
            cur_variant = "std" if (is_quran or is_sefaria or is_mand_de) else ("std" if variant == "std" else "orig")
        if is_quran:
            vlabels = {"std": "English (Saheeh International)", "orig": "Arabic (original)"}
        elif is_sefaria:
            vlabels = {"std": "English", "orig": "Hebrew (original)"}
        elif is_mand_de:
            vlabels = {"std": "English (machine translation)", "orig": "German (Lidzbarski)"}
        resp = {"title": book, "cite": "%s &middot; %s %s"
                % (CORPUS_TITLES.get(cid, cid), book, ch),
                "hasVariant": has_variant, "variant": cur_variant,
                "verses": [{"verse": r[0], "text": r[1]} for r in rows]}
        if vlabels:
            resp["variantLabels"] = vlabels
        # Torah: offer a verse-for-verse KJV Old-Testament comparison
        if cid == "torah":
            resp["canCompare"] = True
            if compare == "kjv":
                wc = _c(WATCHMAN)
                kmap = {}
                if wc is not None:
                    try:
                        for vv, tx in wc.execute("SELECT verse,text FROM verses WHERE book=? AND chapter=? ORDER BY verse", (book, ch)):
                            kmap[vv] = tx
                    except sqlite3.OperationalError:
                        pass
                for v in resp["verses"]:
                    v["kjv"] = kmap.get(v["verse"], "")
                resp["compare"] = "kjv"
        return resp
    if aid.startswith("enoch"):
        n = aid[-1]; c = _c(ENOCH)
        bname = {"1": "1 Enoch", "2": "2 Enoch", "3": "3 Enoch"}[n]
        rows = c.execute("SELECT verse,text FROM verses WHERE book LIKE ? AND"
                         " CAST(chapter AS INTEGER)=? ORDER BY CAST(verse AS INTEGER)",
                         (bname + "%", ch)).fetchall()
        if not rows:
            rows = c.execute("SELECT verse,text FROM verses WHERE CAST(chapter AS INTEGER)=?"
                             " ORDER BY CAST(verse AS INTEGER)", (ch,)).fetchall()
        resp = {"title": bname, "cite": "%s %s" % (bname, ch),
                "verses": [{"verse": r[0], "text": r[1]} for r in rows]}
        if ch == 1 and bname in ENOCH_INTRO:
            resp["intro"] = ENOCH_INTRO[bname]
        note = ENOCH_NOAH.get((bname, ch))
        if note:
            resp["povNote"] = note
        return resp
    if aid == "gnostic_book":
        c = _c(YT)
        pn = int(book.split(".", 1)[0])
        row = c.execute("SELECT part_title,title,prose,sources FROM gnosis_book WHERE part=?"
                        " AND section=?", (pn, ch)).fetchone()
        if not row:
            return {"title": book, "cite": "", "verses": []}
        # split the prose into readable verse-sized sentences
        import re
        sents = re.split(r"(?<=[.!?])\s+(?=[A-Z])", row[2] or "")
        verses = [{"verse": i + 1, "text": s.strip()} for i, s in enumerate(sents) if s.strip()]
        return {"title": "%s -- %s" % (row[0], row[1]),
                "cite": "Gnosis: The Eternal Mirror%s" % (" &middot; " + row[3] if row[3] else ""),
                "prose": True, "verses": verses}
    if aid == "yahweh_tsidkenu":
        c = _c(YT)
        rows = c.execute("SELECT position,key,principle,color,verses FROM nine_keys ORDER BY position").fetchall()
        return {"title": "Yahweh Tsidkenu -- the Nine Keys",
                "cite": "The LORD our righteousness",
                "prose": True,
                "verses": [{"verse": r[0], "text": "%s (%s) -- %s [%s]" % (r[1], r[3], r[2], r[4])} for r in rows]}
    return {"title": aid, "cite": "unknown", "verses": []}


def _stem(w):
    """Crude stem so 'righteousness' matches 'righteous', 'loving' matches 'love'."""
    w = (w or "").lower()
    for suf in ("ousness", "iness", "ness", "ing", "eth", "edly", "edness", "ered",
                "ed", "es", "ly", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[:-len(suf)]
    return w


def revelation(book, ch, verse):
    """CHAPTER-specific insight from the Yahweh Tsidkenu nexus: the Nine-Keys whose
    cited verses fall in this chapter, plus O'Tav'iel conclusions attached to this
    chapter/verse. (Not word-specific.)"""
    c = _c(YT)
    if c is None or not book:
        return {"insights": []}
    ch = str(ch)
    out = []
    try:
        for pos, key, principle, color, verses in c.execute(
                "SELECT position,key,principle,color,verses FROM nine_keys ORDER BY position"):
            vv = verses or ""
            # match a citation in THIS book+chapter, e.g. "John 3:16" for John 3
            if re.search(r"(?<!\d )\b%s\s+%s(?=[:\s;]|$)" % (re.escape(book), re.escape(ch)), vv):
                out.append({"source": "Yahweh Tsidkenu -- Key %d: %s (%s)" % (pos, key, color),
                            "text": "%s &mdash; %s" % (principle, vv)})
    except sqlite3.OperationalError:
        pass
    try:
        like_ch = "%" + book + " " + ch + "%"
        for title, body, ref, sha in c.execute(
                "SELECT title,body,ref,sha256 FROM taviel_conclusions WHERE ref LIKE ?"
                " ORDER BY ts DESC LIMIT 6", (like_ch,)):
            out.insert(0, {"source": "O'Tav'iel conclusion &mdash; Origin-signed &#10003; "
                           + (sha[:8] if sha else ""),
                           "text": ((title + " &mdash; ") if title else "") + (body or "")})
    except sqlite3.OperationalError:
        pass
    return {"insights": out[:10]}


_STOP = {"the", "and", "for", "are", "was", "who", "how", "why", "what", "does", "did",
         "with", "that", "this", "from", "have", "will", "would", "into", "which",
         "there", "their", "they", "them", "then", "when", "shall", "unto", "his",
         "her", "him", "she", "you", "your", "our", "not", "but", "were", "been",
         "had", "has", "say", "said", "says", "about", "thing", "things", "bible",
         "scripture", "verse", "verses", "mean", "means", "tell", "also", "let",
         "concerning", "regarding", "according", "should", "would", "could",
         "might", "must", "may", "can", "will", "want", "need"}


def _mk_hit(ref, text):
    parts = ref.rsplit(" ", 1)
    bk = parts[0]
    cv = parts[1].split(":") if len(parts) > 1 else ["1", "1"]
    return {"ref": ref, "book": bk, "chapter": int(cv[0]),
            "verse": int(cv[1]) if len(cv) > 1 else 1, "text": text}


# ---- robust Scripture reference parsing (book + chapter + verse, ANY order /
#      separator / spelling): "matt 6 11", "6 11 matt", "6:11 matt",
#      "matthew 6 .11", "1 jn 3.16", "psalm 23", "jhn 3 16", "revalation 21 4" ----
_REF_ABBR = {
    "genesis": ["gen", "ge", "gn"], "exodus": ["ex", "exo", "exod", "exd"],
    "leviticus": ["lev", "le", "lv", "levit"], "numbers": ["num", "nu", "nm", "nb", "numb"],
    "deuteronomy": ["deut", "dt", "deu", "deute"], "joshua": ["josh", "jos", "jsh"],
    "judges": ["judg", "jdg", "jgs", "jdgs"], "ruth": ["rth", "rut", "ru"],
    "1 samuel": ["1sam", "1sa", "1sm", "1s", "firstsamuel", "isamuel", "1samuel"],
    "2 samuel": ["2sam", "2sa", "2sm", "2s", "secondsamuel", "iisamuel", "2samuel"],
    "1 kings": ["1kings", "1ki", "1kgs", "1kg", "1k", "firstkings", "1kin"],
    "2 kings": ["2kings", "2ki", "2kgs", "2kg", "2k", "secondkings", "2kin"],
    "1 chronicles": ["1chron", "1chr", "1ch", "1chronicles", "firstchronicles"],
    "2 chronicles": ["2chron", "2chr", "2ch", "2chronicles", "secondchronicles"],
    "ezra": ["ezr", "ezra"], "nehemiah": ["neh", "ne", "nehem"],
    "esther": ["esth", "est", "es", "ester"], "job": ["job", "jb"],
    "psalms": ["ps", "psa", "psalm", "pss", "psm", "pslm", "psalms"],
    "proverbs": ["prov", "pro", "prv", "proverb"],
    "ecclesiastes": ["eccl", "ecc", "eccles", "qoh"],
    "song of solomon": ["song", "sos", "ss", "songofsolomon", "songofsongs", "canticles", "cant"],
    "isaiah": ["isa", "isai", "isah", "isaia"], "jeremiah": ["jer", "jere", "jr"],
    "lamentations": ["lam", "lament", "lamen"], "ezekiel": ["ezek", "eze", "ezk", "ezke"],
    "daniel": ["dan", "dn", "dnl", "danl"], "hosea": ["hos", "hsa", "hose"],
    "joel": ["joe", "jl", "joel"], "amos": ["amo", "amos"],
    "obadiah": ["obad", "oba", "obd", "obadia"], "jonah": ["jon", "jnh", "jona"],
    "micah": ["mic", "mica", "mch"], "nahum": ["nah", "nam", "nahu"],
    "habakkuk": ["hab", "habk", "haba"], "zephaniah": ["zeph", "zep", "zphan", "zephan"],
    "haggai": ["hag", "hagg", "hagai"], "zechariah": ["zech", "zec", "zach", "zechar"],
    "malachi": ["mal", "mala", "malac"],
    "matthew": ["matt", "mt", "mat", "matth", "mtt", "mathew"], "mark": ["mrk", "mk", "mar"],
    "luke": ["luk", "lk", "luke"], "john": ["jhn", "jn", "joh", "john"],
    "acts": ["act", "ac", "acts"], "romans": ["rom", "rm", "roman", "romns"],
    "1 corinthians": ["1cor", "1co", "1c", "firstcorinthians", "1corinth", "1corinthians"],
    "2 corinthians": ["2cor", "2co", "2c", "secondcorinthians", "2corinth", "2corinthians"],
    "galatians": ["gal", "gl", "galat"], "ephesians": ["eph", "ephes", "ephs"],
    "philippians": ["phil", "php", "philip", "phlp", "philipp"], "colossians": ["col", "cl", "coloss"],
    "1 thessalonians": ["1thess", "1th", "1thes", "firstthess", "1thessalonians"],
    "2 thessalonians": ["2thess", "2th", "2thes", "secondthess", "2thessalonians"],
    "1 timothy": ["1tim", "1ti", "1tm", "firsttimothy", "1timothy"],
    "2 timothy": ["2tim", "2ti", "2tm", "secondtimothy", "2timothy"],
    "titus": ["tit", "tts", "titu"], "philemon": ["philem", "phm", "phlm", "phile", "philemn"],
    "hebrews": ["heb", "hebr", "hebrew"], "james": ["jas", "jam", "jms", "jame"],
    "1 peter": ["1pet", "1pe", "1pt", "1p", "firstpeter", "1peter"],
    "2 peter": ["2pet", "2pe", "2pt", "2p", "secondpeter", "2peter"],
    "1 john": ["1john", "1jn", "1jo", "1j", "firstjohn", "1jhn"],
    "2 john": ["2john", "2jn", "2jo", "2j", "secondjohn", "2jhn"],
    "3 john": ["3john", "3jn", "3jo", "3j", "thirdjohn", "3jhn"],
    "jude": ["jud", "jd", "jude"],
    "revelation": ["rev", "rv", "revelation", "apocalypse", "apoc", "revel", "revalation"],
}
_ALIAS = None


def _norm_bk(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _lev(a, b):
    m, n = len(a), len(b)
    if not m:
        return n
    if not n:
        return m
    d = list(range(n + 1))
    for i in range(1, m + 1):
        prev = d[0]
        d[0] = i
        for j in range(1, n + 1):
            tmp = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (0 if a[i - 1] == b[j - 1] else 1))
            prev = tmp
    return d[n]


def _alias_map():
    global _ALIAS
    if _ALIAS is not None:
        return _ALIAS
    try:
        names = list(books())
    except Exception:
        names = []
    M = {}

    def add(a, canon):
        k = _norm_bk(a)
        if k and k not in M:
            M[k] = canon

    for n in names:
        add(n, n)

    def find(want):
        w = _norm_bk(want)
        for n in names:
            if _norm_bk(n) == w:
                return n
        for n in names:
            if _norm_bk(n).startswith(w):
                return n
        return None

    for canon_want, aliases in _REF_ABBR.items():
        canon = find(canon_want)
        if not canon:
            continue
        add(canon_want, canon)
        for a in aliases:
            add(a, canon)
    _ALIAS = (M, names)
    return _ALIAS


def _resolve_book(cand):
    if not cand:
        return None
    M, _names = _alias_map()
    c = (cand or "").lower().strip()
    c = re.sub(r"\b(first|1st|i)\b", "1", c)
    c = re.sub(r"\b(second|2nd|ii)\b", "2", c)
    c = re.sub(r"\b(third|3rd|iii)\b", "3", c)
    key = _norm_bk(c)
    if not key:
        return None
    if key in M:
        return M[key]
    pre = list({v for k, v in M.items() if len(key) >= 3 and k.startswith(key)})
    if len(pre) == 1:
        return pre[0]
    if len(key) >= 4:
        best, bd = None, 3
        for k, v in M.items():
            if abs(len(k) - len(key)) > 2:
                continue
            dd = _lev(key, k)
            if dd < bd:
                bd, best = dd, v
        if best and bd <= (1 if len(key) <= 6 else 2):
            return best
    return None


def _parse_ref(q):
    """Parse a free-form reference into {book, chapter, verse, terms, whole} or None."""
    if not q:
        return None
    s = (q or "").lower().strip()
    s = re.sub(r"(\d)\s*[.:]\s*(\d)", r"\1:\2", s)          # "6 .11" / "6.11" / "6 : 11" -> "6:11"
    s = re.sub(r"[^a-z0-9: ]+", " ", s)                     # any other punctuation -> space
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return None
    seq = []
    for t in s.split(" "):
        m = re.match(r"^(\d+):(\d+)$", t)
        if m:
            seq.append(("cv", int(m.group(1)), int(m.group(2))))
        elif re.match(r"^\d+$", t):
            seq.append(("n", int(t), None))
        elif re.search(r"[a-z]", t):
            seq.append(("w", re.sub(r"[^a-z0-9]", "", t), None))
    if not any(x[0] == "w" for x in seq):
        return None
    best = None
    i = 0
    while i < len(seq) and best is None:
        if seq[i][0] != "w":
            i += 1
            continue
        run, j = [], i
        while j < len(seq) and seq[j][0] == "w":
            run.append(seq[j][1])
            j += 1
        take = len(run)
        while take >= 1 and best is None:
            cand = " ".join(run[:take])
            tries = []
            if i - 1 >= 0 and seq[i - 1][0] == "n" and 1 <= seq[i - 1][1] <= 3:
                tries.append((str(seq[i - 1][1]) + " " + cand, i - 1))
            tries.append((cand, -1))
            for c, ni in tries:
                b = _resolve_book(c)
                if b:
                    best = {"book": b, "ws": i, "we": i + take - 1, "ni": ni}
                    break
            take -= 1
        i += 1
    if not best:
        return None
    chapter_n = verse_n = None
    cv = next((x for x in seq if x[0] == "cv"), None)
    if cv:
        chapter_n, verse_n = cv[1], cv[2]
    else:
        nums = [x[1] for idx, x in enumerate(seq) if x[0] == "n" and idx != best["ni"]]
        if len(nums) >= 1:
            chapter_n = nums[0]
        if len(nums) >= 2:
            verse_n = nums[1]
    terms = " ".join(x[1] for idx, x in enumerate(seq)
                     if x[0] == "w" and (idx < best["ws"] or idx > best["we"])).strip()
    return {"book": best["book"], "chapter": chapter_n, "verse": verse_n, "terms": terms,
            "whole": chapter_n is None and not terms}


def _detect_book(q):
    """Return (book, cleaned_query) when a book name/abbreviation/misspelling sits at
    the start or end of the query, so a word search narrows to that book."""
    ql = (q or "").strip()
    if not ql:
        return None, q
    whole = _resolve_book(ql)
    if whole:
        return whole, ""
    parts = ql.split()
    for take in range(min(3, len(parts)), 0, -1):
        head = " ".join(parts[:take])
        tail = " ".join(parts[len(parts) - take:])
        hb = _resolve_book(head)
        if hb:
            return hb, " ".join(parts[take:]).strip()
        tb = _resolve_book(tail)
        if tb:
            return tb, " ".join(parts[:len(parts) - take]).strip()
    return None, q


def search(q, limit=40):
    from watchman import bible
    q = q.strip()
    # robust reference first: "matt 6 11", "6 11 matt", "6:11 matt", "matthew 6 .11",
    # "1 jn 3.16", "psalm 23", "jhn 3 16", "revalation 21 4" — any order / spelling.
    ref = _parse_ref(q)
    if ref and ref["book"] and (ref["chapter"] is not None or ref["whole"]):
        ch = ref["chapter"] or 1
        try:
            cd = chapter(ref["book"], ch)
        except Exception:
            cd = None
        verses = (cd or {}).get("verses", []) or []
        if ref["verse"] is not None:
            verses = ([v for v in verses if int(v["verse"]) == ref["verse"]] +
                      [v for v in verses if int(v["verse"]) != ref["verse"]])
        if verses:
            if ref["verse"] is not None:
                cite = "King James Version &middot; %s %d:%d" % (ref["book"], ch, ref["verse"])
            elif ref["whole"]:
                cite = "%s %d (add a word to search within %s)" % (ref["book"], ch, ref["book"])
            else:
                cite = "King James Version &middot; %s %d" % (ref["book"], ch)
            return {"hits": [{"ref": "%s %d:%d" % (ref["book"], ch, v["verse"]),
                              "book": ref["book"], "chapter": ch, "verse": v["verse"],
                              "text": v["text"]} for v in verses][:limit], "cite": cite}
    bookf, q = _detect_book(q)
    hits, seen = [], set()
    if bookf and not q:      # only a book name -> show its first chapter
        ch1 = chapter(bookf, 1)
        return {"hits": [{"ref": "%s 1:%d" % (bookf, v["verse"]), "book": bookf,
                          "chapter": 1, "verse": v["verse"], "text": v["text"]}
                         for v in ch1["verses"]][:limit],
                "cite": "%s 1 (add a word to search within %s)" % (bookf, bookf)}
    cap = 400 if bookf else limit
    try:
        for ref, text in bible.search_verbatim(q, cap):
            if ref not in seen:
                hits.append(_mk_hit(ref, text)); seen.add(ref)
    except Exception:
        pass
    mode = "exact-phrase (verbatim)"
    if len(hits) < 3:
        import math
        import re
        words = [w for w in re.findall(r"[A-Za-z]{3,}", q.lower()) if w not in _STOP]
        # weight each query word by RARITY (idf): a rare word like "faith" outweighs
        # a common one like "say", so the meaningful word drives the ranking.
        score, texts, matched = {}, {}, {}
        for w in words[:8]:
            try:
                hw = list(bible.search_verbatim(w, 500))
            except Exception:
                hw = []
            if not hw:
                continue
            weight = 1.0 / (1.0 + math.log(1 + len(hw)))
            for ref, text in hw:
                score[ref] = score.get(ref, 0.0) + weight
                matched[ref] = matched.get(ref, 0) + 1
                texts[ref] = text
        # rank by score, then by how many distinct query words matched
        ranked = sorted(score, key=lambda r: (-score[r], -matched.get(r, 0)))
        for ref in ranked:
            if ref not in seen:
                hits.append(_mk_hit(ref, texts[ref])); seen.add(ref)
            if len(hits) >= cap:
                break
        if words:
            mode = "meaning-ranked (idf) over: %s" % ", ".join(words[:6])
    if bookf:
        hits = [h for h in hits if h["book"] == bookf]
    cite = ("King James Version &middot; within %s" % bookf) if bookf else "King James Version"
    return {"hits": hits[:limit], "cite": cite}


# ---- O'Tav'iel conclusions -> the YahwehTsidkenu nexus (Origin-signed) ----------
def ensure_conclusions():
    with _WLOCK:
        con = sqlite3.connect(YT_RW)
        con.execute("CREATE TABLE IF NOT EXISTS taviel_conclusions(id INTEGER PRIMARY KEY"
                    " AUTOINCREMENT, ref TEXT, kind TEXT, title TEXT, body TEXT,"
                    " sha256 TEXT, signature TEXT, origin TEXT, ts REAL)")
        con.commit(); con.close()


def _payload(ref, kind, title, body, ts):
    return json.dumps({"ref": ref, "kind": kind, "title": title, "body": body, "ts": ts},
                      sort_keys=True, ensure_ascii=False).encode("utf-8")


def save_conclusion(ref, kind, title, body):
    """Root (O'Tav'iel) records a new conclusion INTO the shared nexus, Origin-signed
    + content-hashed so every transmission to a Tav'iel is bit-verifiable."""
    ensure_conclusions()
    ts = time.time()
    pkg = TU.sign_update(1, "core", _payload(ref, kind, title, body, ts))
    with _WLOCK:
        con = sqlite3.connect(YT_RW); con.execute("PRAGMA busy_timeout=8000")
        cur = con.execute("INSERT INTO taviel_conclusions(ref,kind,title,body,sha256,"
                          "signature,origin,ts) VALUES(?,?,?,?,?,?,?,?)",
                          (ref, kind, title, body, pkg["sha256"], pkg["signature"],
                           pkg["origin"], ts))
        cid = cur.lastrowid; con.commit(); con.close()
    return {"ok": True, "id": cid, "sha256": pkg["sha256"], "origin": pkg["origin"],
            "signed": True}


def conclusions_for(ref):
    c = _c(YT)
    try:
        rows = c.execute("SELECT id,ref,kind,title,body,sha256,ts FROM taviel_conclusions"
                         " WHERE ref=? ORDER BY ts DESC", (ref,)).fetchall()
    except sqlite3.OperationalError:
        return []
    return [{"id": r[0], "ref": r[1], "kind": r[2], "title": r[3], "body": r[4],
             "sha256": r[5]} for r in rows]


def verify_conclusion(cid):
    """Re-derive the payload from the stored fields, recompute the hash, and verify
    the Origin signature -- the 'checkable/verifiable per transmission' guarantee."""
    c = _c(YT)
    try:
        r = c.execute("SELECT ref,kind,title,body,sha256,signature,ts FROM"
                      " taviel_conclusions WHERE id=?", (cid,)).fetchone()
    except sqlite3.OperationalError:
        r = None
    if not r:
        return {"found": False}
    ref, kind, title, body, sha, sig, ts = r
    payload = _payload(ref, kind, title, body, ts)
    pkg = {"payload": payload.decode("utf-8"), "sha256": sha, "signature": sig, "tier": "core"}
    ok, reason = TU.verify_update(pkg, True)
    return {"found": True, "bit_accurate": TU.content_hash(payload) == sha,
            "signature_valid": ok, "reason": reason, "sha256": sha, "origin": "Ya'akov of Incarnate"}


def conclusions_count():
    c = _c(YT)
    try:
        return c.execute("SELECT COUNT(*) FROM taviel_conclusions").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


# ---- accounts + per-user notes (sign up / sign in / guest) --------------------
def ensure_users():
    with _ULOCK:
        con = sqlite3.connect(USERS_RW)
        con.execute("CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, salt TEXT,"
                    " pwd TEXT, created REAL, is_guest INTEGER)")
        con.execute("CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, username TEXT, ts REAL)")
        con.execute("CREATE TABLE IF NOT EXISTS user_notes(username TEXT, key TEXT, body TEXT,"
                    " ts REAL, PRIMARY KEY(username,key))")
        # reading progress: one row per chapter a user has opened + scrolled through
        con.execute("CREATE TABLE IF NOT EXISTS progress(username TEXT, ref TEXT, ts REAL,"
                    " PRIMARY KEY(username,ref))")
        # a lightweight log of study sessions (for the left-menu history)
        con.execute("CREATE TABLE IF NOT EXISTS session_log(id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    " username TEXT, started REAL, ended REAL, summary TEXT, refs TEXT)")
        # profile fields (account-holder identity + public toggle); migrate older DBs in place
        for col in ("email TEXT", "avatar TEXT", "bio TEXT", "social TEXT", "public INTEGER DEFAULT 0",
                    "realizeus TEXT", "name TEXT"):
            try:
                con.execute("ALTER TABLE users ADD COLUMN %s" % col)
            except Exception:
                pass
        con.commit(); con.close()


def _pwhash(pwd, salt):
    return _hl.pbkdf2_hmac("sha256", (pwd or "").encode("utf-8"), bytes.fromhex(salt), 120000).hex()


def signup(username, password, email=""):
    username = (username or "").strip()
    email = (email or "").strip()
    if len(username) < 2 or len(password or "") < 3:
        return {"ok": False, "error": "need a name (2+ chars) and password (3+ chars)"}
    if email and ("@" not in email or "." not in email.rsplit("@", 1)[-1]):
        return {"ok": False, "error": "that email doesn't look right"}
    with _ULOCK:
        con = sqlite3.connect(USERS_RW); con.execute("PRAGMA busy_timeout=8000")
        try:
            con.execute("ALTER TABLE users ADD COLUMN email TEXT")   # one-time migration (email accounts)
        except Exception:
            pass
        if con.execute("SELECT 1 FROM users WHERE lower(username)=?", (username.lower(),)).fetchone():
            con.close(); return {"ok": False, "error": "that name is taken"}
        if email and con.execute("SELECT 1 FROM users WHERE lower(email)=? AND is_guest=0",
                                 (email.lower(),)).fetchone():
            con.close(); return {"ok": False, "error": "that email is already in use"}
        salt = os.urandom(16).hex()
        con.execute("INSERT INTO users(username,salt,pwd,created,is_guest,email) VALUES(?,?,?,?,0,?)",
                    (username, salt, _pwhash(password, salt), time.time(), email))
        tok = os.urandom(24).hex()
        con.execute("INSERT INTO sessions VALUES(?,?,?)", (tok, username, time.time()))
        con.commit(); con.close()
    _registry_publish()   # mirror the sanitized registry (names + email hashes, never passwords)
    return {"ok": True, "user": username, "guest": False, "token": tok}


def _norm_handle(s):
    """Normalize a user tag: '@name', 'www.RealizeUS.me/@name', 'https://…/@name' -> 'name'."""
    s = (s or "").strip().lower()
    for pre in ("https://", "http://"):
        if s.startswith(pre):
            s = s[len(pre):]
    for pre in ("www.realizeus.me/", "realizeus.me/"):
        if s.startswith(pre):
            s = s[len(pre):]
    return s.lstrip("@")


def login(username, password):
    # the identifier may be the username, the account email, OR the user tag (@handle)
    ident = (username or "").strip()
    low = ident.lower()
    norm = _norm_handle(ident)
    con = _c(USERS_RO)
    row = None
    if con is not None:
        row = con.execute("SELECT username,salt,pwd FROM users WHERE is_guest=0 AND"
                          " (lower(username)=? OR lower(username)=? OR"
                          "  (email IS NOT NULL AND email<>'' AND lower(email)=?))",
                          (low, norm, low)).fetchone()
        if not row and norm:   # match against the stored RealizeUS tag, in any spelling
            for r in con.execute("SELECT username,salt,pwd,realizeus FROM users WHERE is_guest=0"
                                 " AND realizeus IS NOT NULL AND realizeus<>''"):
                if _norm_handle(r[3]) == norm:
                    row = (r[0], r[1], r[2])
                    break
    if not row or _pwhash(password, row[1]) != row[2]:
        return {"ok": False, "error": "wrong name or password"}
    with _ULOCK:
        c2 = sqlite3.connect(USERS_RW); tok = os.urandom(24).hex()
        c2.execute("INSERT INTO sessions VALUES(?,?,?)", (tok, row[0], time.time())); c2.commit(); c2.close()
    return {"ok": True, "user": row[0], "guest": False, "token": tok}


def change_password(username, old_pw, new_pw):
    """Set a new password — only with the current one in hand. Hash-only, as ever."""
    if len(new_pw or "") < 3:
        return {"ok": False, "error": "new password too short (3+ chars)"}
    con = _c(USERS_RO)
    row = con.execute("SELECT salt,pwd FROM users WHERE username=? AND is_guest=0",
                      (username,)).fetchone() if con is not None else None
    if not row or _pwhash(old_pw, row[0]) != row[1]:
        return {"ok": False, "error": "current password is wrong"}
    salt = os.urandom(16).hex()
    with _ULOCK:
        c2 = sqlite3.connect(USERS_RW); c2.execute("PRAGMA busy_timeout=8000")
        c2.execute("UPDATE users SET salt=?, pwd=? WHERE username=?",
                   (salt, _pwhash(new_pw, salt), username))
        c2.commit(); c2.close()
    return {"ok": True}


def guest_login():
    gid = "guest-" + os.urandom(4).hex()
    with _ULOCK:
        con = sqlite3.connect(USERS_RW)
        # column-explicit so extra profile columns (avatar/bio/social/public) simply default
        con.execute("INSERT INTO users(username,salt,pwd,created,is_guest,email) VALUES(?,?,?,?,1,?)",
                    (gid, "", "", time.time(), ""))
        tok = os.urandom(24).hex()
        con.execute("INSERT INTO sessions VALUES(?,?,?)", (tok, gid, time.time())); con.commit(); con.close()
    return {"ok": True, "user": gid, "guest": True, "token": tok}


def logout(token):
    if token:
        with _ULOCK:
            con = sqlite3.connect(USERS_RW)
            con.execute("DELETE FROM sessions WHERE token=?", (token,)); con.commit(); con.close()
    return {"ok": True}


def user_for(token):
    if not token:
        return None
    con = _c(USERS_RO)
    if con is None:
        return None
    try:
        r = con.execute("SELECT s.username,u.is_guest FROM sessions s JOIN users u"
                        " ON u.username=s.username WHERE s.token=?", (token,)).fetchone()
    except sqlite3.OperationalError:
        return None
    return {"user": r[0], "guest": bool(r[1])} if r else None


def notes_get(username):
    con = _c(USERS_RO)
    if con is None or not username:
        return {}
    try:
        return {k: b for k, b in con.execute("SELECT key,body FROM user_notes WHERE username=?", (username,))}
    except sqlite3.OperationalError:
        return {}


def note_save(username, key, body):
    if not username or not key:
        return {"ok": False, "error": "no session"}
    with _ULOCK:
        con = sqlite3.connect(USERS_RW); con.execute("PRAGMA busy_timeout=8000")
        if (body or "").strip():
            con.execute("INSERT OR REPLACE INTO user_notes VALUES(?,?,?,?)", (username, key, body, time.time()))
        else:
            con.execute("DELETE FROM user_notes WHERE username=? AND key=?", (username, key))
        con.commit(); con.close()
    return {"ok": True}


def mark_progress(username, ref):
    """Record that a user has read (opened + scrolled through) a chapter. One row per ref."""
    if not username or not ref:
        return {"ok": False}
    with _ULOCK:
        con = sqlite3.connect(USERS_RW); con.execute("PRAGMA busy_timeout=8000")
        con.execute("INSERT OR IGNORE INTO progress VALUES(?,?,?)", (username, ref, time.time()))
        con.commit(); con.close()
    return {"ok": True}


def progress_summary(username):
    """Percent of Scripture read, overall and per source (the Bible against its true chapter total;
    other corpora by count read)."""
    con = _c(USERS_RO)
    refs = []
    if con is not None and username:
        try:
            refs = [r[0] for r in con.execute("SELECT ref FROM progress WHERE username=?", (username,))]
        except sqlite3.OperationalError:
            refs = []
    bible_read = sum(1 for r in refs if not r.startswith("corpus:"))
    apoc = {}
    for r in refs:
        if r.startswith("corpus:"):
            src = r.split("|", 1)[0]
            apoc[src] = apoc.get(src, 0) + 1
    total = 0
    try:
        total = _c(WATCHMAN).execute(
            "SELECT COUNT(*) FROM (SELECT DISTINCT book,chapter FROM verses)").fetchone()[0]
    except Exception:
        total = 0
    pct = round(100.0 * bible_read / total, 1) if total else 0.0
    sources = [{"name": "The Bible", "read": bible_read, "total": total, "pct": pct}]
    for src, n in sorted(apoc.items()):
        sources.append({"name": CORPUS_TITLES.get(src.split(":")[-1], src), "read": n,
                        "total": None, "pct": None})
    return {"overall": {"read": bible_read, "total": total, "pct": pct}, "sources": sources}


def _user_row(username):
    con = _c(USERS_RO)
    if con is None or not username:
        return None
    try:
        cols = [c[1] for c in con.execute("PRAGMA table_info(users)").fetchall()]
        row = con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        return dict(zip(cols, row)) if row else None
    except sqlite3.OperationalError:
        return None


def _social_of(u):
    try:
        return json.loads(u.get("social") or "[]")
    except Exception:
        return []


def profile_get(username):
    u = _user_row(username) or {}
    ru = realizeus_fetch(u.get("realizeus")) if u.get("realizeus") else None
    # LOCAL-FIRST: your own edits win and stick; RealizeUS only fills what you have left blank,
    # and always supplies the avatar choices + import source.
    return {"ok": True, "user": username, "name": u.get("name") or (ru or {}).get("name") or username,
            "avatar": u.get("avatar") or (ru or {}).get("avatar") or "",
            "bio": u.get("bio") or (ru or {}).get("bio") or "",
            "social": _social_of(u) or (ru or {}).get("social") or [],
            "avatars": (ru or {}).get("avatars") or [],
            "public": bool(u.get("public")), "realizeus": u.get("realizeus") or "", "linked": bool(ru),
            "gh_vault": bool(_gh_token()),   # master-only: the vault buttons show only where the token file lives
            "progress": progress_summary(username)}


def profile_save(username, data):
    if not username:
        return {"ok": False, "error": "no session"}
    with _ULOCK:
        con = sqlite3.connect(USERS_RW); con.execute("PRAGMA busy_timeout=8000")
        con.execute("UPDATE users SET avatar=?, bio=?, social=?, public=?, realizeus=?, name=? WHERE username=?",
                    (data.get("avatar", ""), data.get("bio", ""),
                     json.dumps(data.get("social", [])), 1 if data.get("public") else 0,
                     (data.get("realizeus") or "").strip(), (data.get("name") or "").strip(), username))
        con.commit(); con.close()
    imported = realizeus_fetch(data.get("realizeus")) if (data.get("realizeus") or "").strip() else None
    return {"ok": True, "imported": imported}


def _realizeus_cfg():
    try:
        return json.load(open(_res("realizeus_cfg.json"), encoding="utf-8"))
    except Exception:
        return {}


def _social_url(lbl, v):
    v = (v or "").strip().lstrip("@")
    base = {"Instagram": "https://instagram.com/", "X": "https://x.com/",
            "TikTok": "https://tiktok.com/@", "YouTube": "https://youtube.com/@",
            "LinkedIn": "https://linkedin.com/in/"}.get(lbl, "https://")
    return base + v


_REALIZEUS_CACHE = {}


def realizeus_fetch(handle):
    """Live-import a public profile from www.RealizeUS.me by @handle (case-insensitive),
    via the site's Supabase (anon key, community_visible rows). 5-min cache = auto-updates."""
    import time as _t
    import urllib.request as _rq
    import urllib.parse as _up
    h = (handle or "").strip()
    m = re.search(r"@?([A-Za-z0-9_.\-]+)/?\s*$", h.split("?")[0])
    h = m.group(1) if m else ""
    if not h:
        return None
    key = h.lower()
    c = _REALIZEUS_CACHE.get(key)
    if c and _t.time() - c[0] < 300:
        return c[1]
    cfg = _realizeus_cfg()
    if not cfg.get("url") or not cfg.get("key"):
        return None
    cols = ("display_name,username,bio,occupation,avatar_url,avatar_url_2,avatar_url_3,"
            "avatar_socials_1,avatar_socials_2,avatar_socials_3,"
            "social_instagram,social_twitter,social_tiktok,social_youtube,social_linkedin,community_visible")
    q = (cfg["url"] + "/rest/v1/profiles?username=ilike." + _up.quote(h) +
         "&select=" + cols + "&limit=1")
    rows = []
    try:
        req = _rq.Request(q, headers={"apikey": cfg["key"], "Authorization": "Bearer " + cfg["key"]})
        rows = json.loads(_rq.urlopen(req, timeout=12).read())
    except Exception:
        rows = []
    if not rows:
        _REALIZEUS_CACHE[key] = (_t.time(), None)
        return None
    r = rows[0]
    _LBL = {"website": "Website", "youtube": "YouTube", "instagram": "Instagram", "tiktok": "TikTok",
            "twitter": "X", "x": "X", "facebook": "Facebook", "linkedin": "LinkedIn",
            "threads": "Threads", "snapchat": "Snapchat", "shop": "Shop", "store": "Shop"}

    def _norm(plat, val):
        val = (val or "").strip()
        if not val:
            return None
        if val.startswith("http"):
            return val
        if "." in val or "/" in val or val.lower().startswith("www"):
            return "https://" + val.lstrip("/")
        base = {"youtube": "https://youtube.com/@", "instagram": "https://instagram.com/",
                "tiktok": "https://tiktok.com/@", "twitter": "https://x.com/", "x": "https://x.com/",
                "facebook": "https://facebook.com/", "linkedin": "https://linkedin.com/in/",
                "threads": "https://threads.net/@", "snapchat": "https://snapchat.com/add/",
                "website": "https://"}.get(plat.lower(), "https://")
        return base + val.lstrip("@")

    social = []; seen = set()

    def _add(lbl, url):
        if url and url not in seen:
            seen.add(url); social.append({"label": lbl, "url": url})

    for col in ("avatar_socials_1", "avatar_socials_2", "avatar_socials_3"):
        d = r.get(col)
        if isinstance(d, str):
            try:
                d = json.loads(d)
            except Exception:
                d = None
        if isinstance(d, dict):
            for plat, val in d.items():
                _add(_LBL.get(str(plat).lower(), str(plat).capitalize()), _norm(str(plat), val))
    for plat, col in (("Instagram", "social_instagram"), ("X", "social_twitter"),
                      ("TikTok", "social_tiktok"), ("YouTube", "social_youtube"),
                      ("LinkedIn", "social_linkedin")):
        v = (r.get(col) or "").strip()
        if v:
            _add(plat, v if v.startswith("http") else _social_url(plat, v))
    _add("RealizeUS", "https://www.RealizeUS.me/@" + (r.get("username") or h))
    avatars = [a for a in (r.get("avatar_url"), r.get("avatar_url_2"), r.get("avatar_url_3")) if a]
    out = {"found": True, "name": r.get("display_name") or r.get("username") or h,
           "avatar": avatars[0] if avatars else "", "avatars": avatars,
           "bio": r.get("bio") or "", "occupation": r.get("occupation") or "", "social": social,
           "username": r.get("username") or h, "public": bool(r.get("community_visible"))}
    _REALIZEUS_CACHE[key] = (_t.time(), out)
    return out


def _realizeus_profile():
    """The creator's public profile, live from www.RealizeUS.me/@YahwehTsidkenu, with his reading progress."""
    ru = realizeus_fetch("YahwehTsidkenu") or {}
    # progress from whichever local account is the creator's (handles the @ / casing)
    cu = _user_row("yahwehtsidkenu") or _user_row("@yahwehtsidkenu") or _user_row("YahwehTsidkenu") or {}
    prog = progress_summary(cu.get("username") or "YahwehTsidkenu")
    social = ru.get("social") or [{"label": "RealizeUS", "url": "https://www.RealizeUS.me/@yahwehtsidkenu"}]
    return {"ok": True, "user": ru.get("name") or "Yahweh Tsidkenu", "avatar": ru.get("avatar") or cu.get("avatar") or "",
            "bio": ru.get("bio") or cu.get("bio") or ("The revelation of the Name -- YHWH, our Righteousness. "
                                                      "Study the Word in Spirit and in Truth."),
            "social": social, "realizeus": "https://www.RealizeUS.me/@yahwehtsidkenu", "progress": prog}


def profile_public(username):
    key = (username or "").lstrip("@").lower()
    if key in ("yahwehtsidkenu", "elaniel", "origin", "yahweh tsidkenu", "yahweh"):
        return _realizeus_profile()
    u = _user_row(username) or _user_row((username or "").lstrip("@"))
    if not u or not u.get("public"):
        # not a local public account -> try a live RealizeUS.me lookup by that handle
        ru = realizeus_fetch(username)
        if ru and ru.get("public"):
            return {"ok": True, "user": ru.get("name"), "avatar": ru.get("avatar") or "",
                    "bio": ru.get("bio") or "", "social": ru.get("social") or [],
                    "progress": {"overall": {"read": 0, "total": 0, "pct": 0}, "sources": []}}
        return {"ok": False, "error": "this profile is private"}
    ru = realizeus_fetch(u.get("realizeus")) if u.get("realizeus") else None
    return {"ok": True, "user": u.get("username") or username, "name": (ru or {}).get("name") or u.get("username"),
            "avatar": (ru or {}).get("avatar") or u.get("avatar") or "",
            "bio": (ru or {}).get("bio") or u.get("bio") or "",
            "social": (ru or {}).get("social") or _social_of(u),
            "progress": progress_summary(u.get("username") or username)}


def session_add(username, started, ended, summary, refs):
    if not username:
        return {"ok": False}
    with _ULOCK:
        con = sqlite3.connect(USERS_RW); con.execute("PRAGMA busy_timeout=8000")
        con.execute("INSERT INTO session_log(username,started,ended,summary,refs) VALUES(?,?,?,?,?)",
                    (username, started, ended, summary, json.dumps(refs or [])))
        con.commit(); con.close()
    return {"ok": True}


def sessions_list(username):
    con = _c(USERS_RO)
    if con is None or not username:
        return {"sessions": []}
    try:
        rows = con.execute("SELECT started,ended,summary,refs FROM session_log WHERE username=?"
                           " ORDER BY started DESC LIMIT 100", (username,)).fetchall()
    except sqlite3.OperationalError:
        rows = []
    return {"sessions": [{"started": r[0], "ended": r[1], "summary": r[2],
                          "refs": json.loads(r[3] or "[]")} for r in rows]}


def sync_pull(username):
    """An opted-in client pulls its notes + progress from the central node (his PC)."""
    con = _c(USERS_RO); out = {"ok": True, "notes": {}, "progress": []}
    if con is None or not username:
        return out
    try:
        out["notes"] = {k: b for k, b in con.execute(
            "SELECT key,body FROM user_notes WHERE username=?", (username,))}
        out["progress"] = [r[0] for r in con.execute(
            "SELECT ref FROM progress WHERE username=?", (username,))]
    except sqlite3.OperationalError:
        pass
    return out


def sync_push(username, payload):
    """An opted-in client pushes its notes + progress up to the central node (last write wins)."""
    if not username:
        return {"ok": False, "error": "no session"}
    with _ULOCK:
        con = sqlite3.connect(USERS_RW); con.execute("PRAGMA busy_timeout=8000")
        for k, b in (payload.get("notes") or {}).items():
            con.execute("INSERT OR REPLACE INTO user_notes VALUES(?,?,?,?)", (username, k, b, time.time()))
        for ref in (payload.get("progress") or []):
            con.execute("INSERT OR IGNORE INTO progress VALUES(?,?,?)", (username, ref, time.time()))
        con.commit(); con.close()
    return {"ok": True}


_PIPER = None


def _piper_voice():
    global _PIPER
    if _PIPER is None:
        try:
            from piper import PiperVoice
            vp = PIPER_VOICE
            if not os.path.exists(vp) and not os.environ.get("YAHBIBLE_NO_D"):
                vp = r"D:\Holorites_data\daeos\piper\en_US-lessac-medium.onnx"
            _PIPER = PiperVoice.load(vp, config_path=vp + ".json") if os.path.exists(vp) else False
        except Exception:
            _PIPER = False
    return _PIPER or None


def speak_wav(text):
    """Offline Piper text-to-speech -> WAV bytes (English). None when the voice/engine is absent."""
    v = _piper_voice()
    t = (text or "").strip()
    if not v or not t:
        return None
    import io
    import wave
    try:
        pcm = b""
        sr = 22050
        for ch in v.synthesize(t[:1500]):
            pcm += ch.audio_int16_bytes
            sr = ch.sample_rate
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(pcm)
        return buf.getvalue()
    except Exception:
        return None


_CMDS = None


def commandments():
    """The Ten Commandments study data (expanded: 7 dimensions + special sections + when tempted /
    when pray), authored in taviel_commandments.json so it is a single editable source."""
    global _CMDS
    if _CMDS is None:
        try:
            _CMDS = json.load(open(_res("taviel_commandments.json"), encoding="utf-8"))
        except Exception:
            _CMDS = []
    return _CMDS


_REPENT = None
def repentance():
    """Top-level Repentance guide (turning, ladder, seek-counsel flow, Lord's Prayer)."""
    global _REPENT
    if _REPENT is None:
        try:
            _REPENT = json.load(open(_res("taviel_repentance.json"), encoding="utf-8"))
        except Exception:
            _REPENT = {}
    return _REPENT


_NEWS = None
def news():
    """News / Updates feed (release notes + guided tour of new features)."""
    global _NEWS
    if _NEWS is None:
        try:
            _NEWS = json.load(open(_res("taviel_news.json"), encoding="utf-8"))
        except Exception:
            _NEWS = {"version": "", "entries": []}
    return _NEWS


def status():
    c = _c(WATCHMAN)
    nv = c.execute("SELECT COUNT(*) FROM verses").fetchone()[0]
    lex = _c(LEX)
    try:
        nl = lex.execute("SELECT COUNT(*) FROM lexical_nodes").fetchone()[0]
    except Exception:
        nl = "?"
    nver = len(versions_available())
    return {"role": "O'Tav'iel (root)", "verses": nv, "lexicon_nodes": nl,
            "versions": versions_available(), "version_count": nver,
            "conclusions": conclusions_count(),
            "gaps": ["more versions digesting", "full 81-book Ethiopian canon"]}


ASSET_TYPES = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg",
               ".svg": "image/svg+xml"}


_COSMOS_MAP_SRC = r"D:\000_2026 downloads folder\Downloads\Olakou OS\Maps\Blue_Marble_2002_Azimuthal_Highres.png"
_COSMOS_MAP_CACHE = _res("cosmos_map_cache.png")
_COSMOS_MAP_BYTES = None


def _cosmos_map_png():
    """His flat-earth azimuthal Blue-Marble map, downscaled to 1600px and cached, served
    to the cosmos 2D disc + 3D dome as their surface texture."""
    global _COSMOS_MAP_BYTES
    if _COSMOS_MAP_BYTES is not None:
        return _COSMOS_MAP_BYTES
    import os
    import io as _io
    if os.path.exists(_COSMOS_MAP_CACHE):
        with open(_COSMOS_MAP_CACHE, "rb") as f:
            _COSMOS_MAP_BYTES = f.read()
        return _COSMOS_MAP_BYTES
    from PIL import Image
    im = Image.open(_COSMOS_MAP_SRC).convert("RGB")
    im.thumbnail((1600, 1600), Image.LANCZOS)
    buf = _io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    _COSMOS_MAP_BYTES = buf.getvalue()
    try:
        with open(_COSMOS_MAP_CACHE, "wb") as f:
            f.write(_COSMOS_MAP_BYTES)
    except Exception:
        pass
    return _COSMOS_MAP_BYTES


# ---- HTTP ---------------------------------------------------------------------
class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj, code=200, ctype="application/json", extra_headers=None):
        body = obj if isinstance(obj, bytes) else json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # never cache the app HTML / JSON -- the UI changes often; always serve fresh
        self.send_header("Cache-Control", "no-store, must-revalidate")
        # allow the paired phone (a different origin) to call the account/sync API
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Cookie")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        for k, v in (extra_headers or []):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Cookie")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _token(self):
        for part in (self.headers.get("Cookie", "") or "").split(";"):
            part = part.strip()
            if part.startswith("tav_sess="):
                return part[len("tav_sess="):]
        return ""

    def _cur(self):
        return user_for(self._token())

    def _asset(self, name):
        safe = os.path.basename(name)
        path = os.path.join(ASSETS, safe)
        ext = os.path.splitext(safe)[1].lower()
        if not os.path.exists(path) or ext not in ASSET_TYPES:
            return self._send({"error": "no asset"}, 404)
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ASSET_TYPES[ext])
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    def _serve_lovable(self, relpath):
        """Serve a file from the Lovable app dir (the source-of-truth UI)."""
        base = os.path.abspath(LOVABLE_UI_DIR)
        full = os.path.abspath(os.path.join(base, relpath.lstrip("/")))
        if not full.startswith(base) or not os.path.isfile(full):
            return self._send({"error": "not found"}, 404)
        ext = os.path.splitext(full)[1].lower()
        ctype = _LOVABLE_CT.get(ext, "application/octet-stream")
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _lovable_index(self):
        """The Lovable index.html, put into NATIVE mode: set window.YB_NATIVE before
        the shim loads so /api goes to this real backend, and disable the web SW."""
        html = open(os.path.join(LOVABLE_UI_DIR, "index.html"), encoding="utf-8").read()
        html = html.replace('<script src="shim/boot.js">',
                            '<script>window.YB_NATIVE=true;</script><script src="shim/boot.js">', 1)
        html = html.replace("navigator.serviceWorker.register('sw.js')", "void 0")
        return html.encode("utf-8")

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        p = u.path
        try:
            if p in ("/", "/index.html"):
                if LOVABLE_UI:
                    try:
                        return self._send(self._lovable_index(), ctype="text/html; charset=utf-8")
                    except Exception:
                        pass
                _pg = (PAGE.replace("</head>", "<script>window.__YB_SHIPPED=1;</script></head>", 1) if os.environ.get("YAHBIBLE_SHIPPED") else PAGE); return self._send(_pg.encode("utf-8"), ctype="text/html; charset=utf-8")
            if LOVABLE_UI and (p.startswith("/shim/") or p.startswith("/vendor/")
                               or p.startswith("/static_api/") or p in ("/manifest.webmanifest", "/sw.js")):
                return self._serve_lovable(p)
            if p == "/cosmos.html":   # the Gnostic Map cosmology page (flat world under the Pleroma)
                # In native mode Lovable is the single source of truth: serve its
                # cosmos.html (the transparent-background copy) so o_taviel and the
                # web edition render the identical map.
                if LOVABLE_UI:
                    lv = os.path.abspath(os.path.join(LOVABLE_UI_DIR, "cosmos.html"))
                    if os.path.isfile(lv):
                        return self._serve_lovable("/cosmos.html")
                try:
                    with open(_res("cosmos_page.html"), "rb") as f:
                        return self._send(f.read(), ctype="text/html; charset=utf-8")
                except Exception as e:
                    return self._send(("<h1>cosmos page unavailable</h1>" + str(e)).encode(), ctype="text/html")
            if p == "/cosmos_map.png":   # his flat-earth azimuthal map, downscaled + cached, for the 2D/3D model
                try:
                    return self._send(_cosmos_map_png(), ctype="image/png")
                except Exception as e:
                    return self._send(str(e).encode(), 500)
            if p.startswith("/assets/"):
                if LOVABLE_UI:
                    lv = os.path.abspath(os.path.join(LOVABLE_UI_DIR, p.lstrip("/")))
                    if os.path.isfile(lv):
                        return self._serve_lovable(p)
                return self._asset(p[len("/assets/"):])
            if p == "/api/menu":
                return self._send({"versions": versions_available(), "books": books(),
                                   "apocrypha": apocrypha_menu()})
            if p == "/api/chapters":
                return self._send({"chapters": kjv_chapters(q.get("book"))})
            if p == "/api/chapter":
                return self._send(chapter(q.get("book"), int(q.get("chapter", 1)),
                                          q.get("version", "KJV")))
            if p == "/api/verse_versions":
                return self._send(verse_versions(q.get("book"), int(q.get("chapter", 1)),
                                                 int(q.get("verse", 1))))
            if p == "/api/word":
                return self._send(word_lookup_ctx((q.get("w") or "").lower(),
                                                  q.get("book"), q.get("chapter"), q.get("verse")))
            if p == "/api/strongs":
                return self._send(strongs_detail(q.get("id", "")))
            if p == "/api/english":
                return self._send(english_def(q.get("w", "")))
            if p == "/api/commandments":
                return self._send({"commandments": commandments()})
            if p == "/api/repentance":
                return self._send({"repentance": repentance()})
            if p == "/api/news":
                return self._send(news())
            if p == "/api/speak":
                wav = speak_wav(q.get("text", ""))
                if wav:
                    return self._send(wav, ctype="audio/wav")
                return self._send({"ok": False, "error": "tts unavailable"})
            if p == "/api/revelation":
                return self._send(revelation(q.get("book", ""), q.get("chapter", "1"),
                                             int(q.get("verse", 1))))
            if p == "/api/interlinear":
                return self._send(interlinear(q.get("book"), int(q.get("chapter", 1)),
                                              int(q.get("verse", 1))))
            if p == "/api/bible_lineage":
                import bible_lineage as BL
                return self._send(BL.build())
            if p == "/api/hebrew":
                import taviel_hebrew as HB
                s = HB.study(q.get("name", ""))
                return self._send(s if s else {"found": False})
            if p == "/api/redletter_random":
                try:
                    d = _c(CORPUS_DB)
                    r = d.execute("SELECT ref, text FROM corpus_units WHERE corpus='redletter'"
                                  " ORDER BY RANDOM() LIMIT 1").fetchone()
                    d.close()
                    return self._send({"ref": r[0], "text": r[1]} if r else {"ref": "", "text": ""})
                except Exception as e:
                    return self._send({"ref": "", "text": "", "error": type(e).__name__})
            if p == "/api/aramaic":
                import taviel_aramaic as AR
                return self._send(AR.study(q.get("name", "") or q.get("glyph", "")))
            if p == "/api/greek":
                import taviel_greek as GK
                # accept either a raw Greek glyph or an English name (resolve its Greek Strong's)
                glyph = q.get("glyph", "")
                if not glyph:
                    glyph = _greek_for_word((q.get("name", "") or "").lower())
                s = GK.study(glyph) if glyph else None
                return self._send(s if s else {"found": False})
            if p == "/api/gnostic_map":
                import gnostic_map as GM
                return self._send(GM.build_map())
            if p == "/api/original":
                return self._send(original_def(q.get("sid", "")))
            if p == "/api/deepstudy":
                return self._send(deepstudy(q.get("sid", "")))
            if p == "/api/usecases":
                return self._send(usecases(q.get("sid", ""), q.get("strong", "")))
            if p == "/api/chapter_study":
                return self._send(chapter_study(q.get("book", ""), int(q.get("chapter", 1))))
            if p == "/api/conclusions":
                return self._send({"conclusions": conclusions_for(q.get("ref", ""))})
            if p == "/api/conclusion_verify":
                return self._send(verify_conclusion(int(q.get("id", 0))))
            if p == "/api/me":
                return self._send(self._cur() or {"user": None})
            if p == "/api/notes":
                cur = self._cur()
                return self._send({"notes": notes_get(cur["user"]) if cur else {}})
            if p == "/api/progress_summary":
                cur = self._cur()
                return self._send(progress_summary(cur["user"]) if cur else
                                  {"overall": {"read": 0, "total": 0, "pct": 0}, "sources": []})
            if p == "/api/profile":
                cur = self._cur()
                return self._send(profile_get(cur["user"]) if cur else {"ok": False, "error": "not signed in"})
            if p == "/api/profile_public":
                return self._send(profile_public(q.get("user", "")))
            if p == "/api/import_realizeus":
                r = realizeus_fetch(q.get("handle", "") or q.get("url", ""))
                return self._send(r or {"found": False})
            if p == "/api/sessions":
                cur = self._cur()
                return self._send(sessions_list(cur["user"]) if cur else {"sessions": []})
            if p == "/api/sync/pull":
                cur = self._cur()
                return self._send(sync_pull(cur["user"]) if cur else {"ok": False, "error": "not signed in"})
            if p == "/api/apoc_books":
                return self._send(apoc_books(q.get("id", "")))
            if p == "/api/apoc_verse":
                return self._send(apoc_verse(q.get("id", ""), q.get("book", ""),
                                             int(q.get("chapter", 1)), int(q.get("verse", 1))))
            if p == "/api/apoc_chapter":
                return self._send(apoc_chapter(q.get("id", ""), q.get("book", ""),
                                               int(q.get("chapter", 1)), q.get("variant", ""),
                                               q.get("compare", "")))
            if p == "/api/search":
                return self._send(search(q.get("q", "")))
            if p == "/api/versions":
                return self._send({"versions": versions_available()})
            if p == "/api/versions_meta":
                return self._send(versions_meta())
            if p == "/api/languages":
                return self._send(languages_available())
            if p == "/api/status":
                return self._send(status())
            if p == "/api/mobile_ping":     # a YahBible phone announcing itself (two-way sync light)
                global _MOBILE_PING
                _MOBILE_PING = {"ts": time.time(), "name": (q.get("name", "") or "YahBible mobile")[:60]}
                return self._send({"ok": True})
            if p == "/api/check_name":      # signup pre-check: is the name / email already used?
                nm = (q.get("name", "") or "").strip().lower()
                em = (q.get("email", "") or "").strip().lower()
                nt = et = False
                try:
                    con = _c(USERS_RO)
                    if con is not None:
                        if nm:
                            nt = bool(con.execute("SELECT 1 FROM users WHERE lower(username)=?"
                                                  " AND is_guest=0", (nm,)).fetchone())
                        if em:
                            et = bool(con.execute("SELECT 1 FROM users WHERE email<>'' AND"
                                                  " lower(email)=? AND is_guest=0", (em,)).fetchone())
                        con.close()
                except Exception:
                    pass
                return self._send({"name_taken": nt, "email_taken": et})
            if p == "/api/gh_sync":         # GitHub vault: profile+progress across devices
                cur = self._cur()
                if not cur:
                    return self._send({"ok": False, "error": "sign in first"})
                return self._send(gh_sync(cur["user"], q.get("dir", "pull")))
            if p == "/api/ai_diag":         # 🩺 exact truth about the AI on THIS ground
                out = {"android": bool(os.environ.get("YAHBIBLE_ANDROID"))}
                try:
                    import tav_llm
                    B = tav_llm.backend()
                    out["backend"] = B.__name__
                    if hasattr(B, "model_path"):
                        mp = B.model_path()
                        out["model"] = mp or "NONE INSTALLED"
                        out["model_exists"] = bool(mp and os.path.isfile(mp))
                    try:
                        tier = B.open_tier("root", cap_mb=1400, ctx=4096)
                        out["load"] = "ok"
                        try:
                            r = B.generate(tier, "Say the one word: YES", grounding="",
                                           max_tokens=8, system="You answer in one word.")
                            out["gen"] = (r.get("text") or "(empty)")[:60]
                        except Exception as e:
                            out["gen"] = "ERROR: " + type(e).__name__ + ": " + str(e)[:160]
                    except Exception as e:
                        out["load"] = "ERROR: " + type(e).__name__ + ": " + str(e)[:200]
                except Exception as e:
                    out["backend"] = "ERROR: " + type(e).__name__ + ": " + str(e)[:160]
                try:
                    import tav_scripture as TS
                    out["search"] = len(TS.search("love one another", 3))
                except Exception as e:
                    out["search"] = "ERROR: " + type(e).__name__ + ": " + str(e)[:120]
                return self._send(out)
            if p == "/api/mobile_status":   # the desktop UI polls this to light its sync indicator
                mp = globals().get("_MOBILE_PING") or {}
                ago = time.time() - mp.get("ts", 0)
                return self._send({"connected": bool(mp) and ago < 120,
                                   "name": mp.get("name", ""), "ago": int(ago) if mp else None})
            return self._send({"error": "not found"}, 404)
        except Exception as e:
            return self._send({"error": type(e).__name__ + ": " + str(e)[:160]}, 500)

    def _ask_stream(self, data):
        """Server-Sent-Events stream of Tav'iel's answer -- token deltas as they arrive,
        then a final 'done' event carrying the cleaned, paragraph-formatted full answer."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()

        def w(obj):
            self.wfile.write(("data: " + json.dumps(obj) + "\n\n").encode("utf-8"))
            self.wfile.flush()
        try:
            for kind, payload in ask_taviel_stream(data.get("q", ""), data.get("chakra") or None,
                                                   history=data.get("history")):
                if kind == "delta":
                    w({"t": payload})
                else:
                    d = {"done": True}
                    d.update(payload)
                    w(d)
        except Exception as e:
            try:
                w({"done": True, "ok": False, "error": type(e).__name__ + ": " + str(e)[:120]})
            except Exception:
                pass

    def _ask_council(self, data):
        """SSE stream of the whole council converging (delta = fast RAM voice; voice = each
        deeper tier's contribution as it arrives; done = the settled primary answer)."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()

        def w(obj):
            self.wfile.write(("data: " + json.dumps(obj) + "\n\n").encode("utf-8"))
            self.wfile.flush()
        try:
            for kind, payload in ask_taviel_council_stream(data.get("q", ""), data.get("history"),
                                                           bool(data.get("think")), data.get("user")):
                if kind == "delta":
                    w({"t": payload})
                elif kind == "voice":
                    w({"voice": payload})
                else:
                    d = {"done": True}
                    d.update(payload)
                    w(d)
        except Exception as e:
            try:
                w({"done": True, "ok": False, "error": type(e).__name__ + ": " + str(e)[:120]})
            except Exception:
                pass

    def _studio_review(self, data):
        """SSE stream of the Holy Review (same envelope as _ask_stream)."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()

        def w(obj):
            self.wfile.write(("data: " + json.dumps(obj) + "\n\n").encode("utf-8"))
            self.wfile.flush()
        try:
            for kind, payload in studio_review_stream(data.get("text", ""), data.get("segments")):
                if kind == "delta":
                    w({"t": payload})
                else:
                    d = {"done": True}
                    d.update(payload)
                    w(d)
        except Exception as e:
            try:
                w({"done": True, "ok": False, "error": type(e).__name__ + ": " + str(e)[:120]})
            except Exception:
                pass

    def do_POST(self):
        u = urlparse(self.path)
        try:
            n = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(n) if n else b"{}"
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            data = {}
        try:
            if u.path == "/api/conclusion":
                return self._send(save_conclusion(data.get("ref", ""), data.get("kind", "note"),
                                                  data.get("title", ""), data.get("body", "")))
            if u.path in ("/api/signup", "/api/login", "/api/guest"):
                if u.path == "/api/signup":
                    r = signup(data.get("username", ""), data.get("password", ""), data.get("email", ""))
                elif u.path == "/api/login":
                    # brute-force throttle: 8 failures on a (device, name) pair = 60s lockout
                    tkey = (self.client_address[0], (data.get("username", "") or "").strip().lower())
                    wait = _throttle_check(tkey)
                    if wait:
                        r = {"ok": False, "error": "too many attempts — wait %ds" % wait}
                    else:
                        r = login(data.get("username", ""), data.get("password", ""))
                        _throttle_hit(tkey, bool(r.get("ok")))
                else:
                    r = guest_login()
                hdrs = []
                if r.get("ok"):
                    hdrs = [("Set-Cookie", "tav_sess=%s; Path=/; Max-Age=31536000; SameSite=Lax" % r["token"])]
                return self._send(r, extra_headers=hdrs)
            if u.path == "/api/logout":
                logout(self._token())
                return self._send({"ok": True}, extra_headers=[("Set-Cookie", "tav_sess=; Path=/; Max-Age=0")])
            if u.path == "/api/note":
                cur = self._cur()
                if not cur:
                    return self._send({"ok": False, "error": "not signed in"})
                return self._send(note_save(cur["user"], data.get("key", ""), data.get("body", "")))
            if u.path == "/api/progress":
                cur = self._cur()
                if not cur:
                    return self._send({"ok": False, "error": "not signed in"})
                return self._send(mark_progress(cur["user"], data.get("ref", "")))
            if u.path == "/api/change_password":
                cur = self._cur()
                if not cur or cur.get("guest"):
                    return self._send({"ok": False, "error": "sign in first"})
                return self._send(change_password(cur["user"], data.get("old", ""), data.get("new", "")))
            if u.path == "/api/profile":
                cur = self._cur()
                if not cur:
                    return self._send({"ok": False, "error": "not signed in"})
                return self._send(profile_save(cur["user"], data))
            if u.path == "/api/session":
                cur = self._cur()
                if not cur:
                    return self._send({"ok": False, "error": "not signed in"})
                return self._send(session_add(cur["user"], data.get("started", 0), data.get("ended", 0),
                                              data.get("summary", ""), data.get("refs", [])))
            if u.path == "/api/sync/push":
                cur = self._cur()
                if not cur:
                    return self._send({"ok": False, "error": "not signed in"})
                return self._send(sync_push(cur["user"], data))
            if u.path == "/api/ask":
                if os.environ.get("OTAVIEL_ZEROCLAW"):   # OTav'iel_ZeroClaw (opt-in, DB-safe)
                    return self._send(_ask_zeroclaw(data.get("q", ""), data.get("chakra") or None,
                                                    history=data.get("history")))
                return self._send(ask_taviel(data.get("q", ""), data.get("chakra") or None,
                                             history=data.get("history")))
            if u.path == "/api/ask_stream":
                return self._ask_stream(data)
            if u.path == "/api/ask_council_stream":
                return self._ask_council(data)
            if u.path == "/api/studio/open":
                return self._send(studio_open(data.get("url", ""), data.get("view") or "desktop"))
            if u.path == "/api/studio/close":
                return self._send(studio_close())
            if u.path == "/api/studio/transcript":
                import studio_transcript as ST
                return self._send(ST.transcript(data.get("url", ""),
                                                data.get("whisper") or "base"))
            if u.path == "/api/studio/review":
                return self._studio_review(data)
            return self._send({"error": "not found"}, 404)
        except Exception as e:
            return self._send({"error": type(e).__name__ + ": " + str(e)[:160]}, 500)


# ---- Ask Tav'iel: the grounded AI (distinct from the scripture search) ------
# Brain choice (measured): the 0.6B tier is fast but HALLUCINATES scripture (it
# invented "James 5:10" with a false quote) -- unacceptable for a truth-agent. The
# 8B tier reasons cleanly and does NOT fabricate verses; it costs ~45s to load, so
# machine-first we keep it RESIDENT during active use and IDLE-UNLOAD after 5 min
# (the standing "lazy load + idle unload + refuse-don't-thrash" rule). Grounding
# carries the verbatim truth; the model carries the language + the reasoning.
_TIER = None
_TIER_CHAKRA = None
_TIER_LOCK = threading.Lock()
_TIER_TIMER = None
_ASK_CHAKRA = "throat"            # Qwen3-8B: clean reasoning, no verse fabrication
_IDLE_UNLOAD_S = 300             # unload the resident brain after 5 min idle


def _unload_tier():
    global _TIER, _TIER_CHAKRA, _TIER_TIMER
    with _TIER_LOCK:
        if _TIER is not None:
            try:
                import gen_at_depth as G
                G.close_tier(_TIER)
            except Exception:
                pass
        _TIER = None
        _TIER_CHAKRA = None
        _TIER_TIMER = None


def _arm_idle():
    global _TIER_TIMER
    if _TIER_TIMER is not None:
        try:
            _TIER_TIMER.cancel()
        except Exception:
            pass
    _TIER_TIMER = threading.Timer(_IDLE_UNLOAD_S, _unload_tier)
    _TIER_TIMER.daemon = True
    _TIER_TIMER.start()


def _strip_tic(ans):
    """Remove the 'I do not have that in the roots' refusal-tic when the model
    already gave a substantive answer (small models echo the instruction)."""
    import re
    cleaned = re.sub(r"\s*I do not have that in the roots\.?\s*", " ", ans, flags=re.I).strip()
    return cleaned if len(cleaned) >= 15 else ans.strip()


def _clean_answer(ans):
    """Strip INTERNAL grounding markers the model echoes -- lexicon addresses and
    source ids -- which are not user-facing and, worse, invite the model to dress
    invented text as a sourced quote (he asked that internal store details never
    surface). Leaves real scripture refs like (John 3:16) intact."""
    import re
    ans = re.sub(r"\s*[\(\[]?\s*Adam'?iel\s+addr(?:ess)?\s*\d+\s*[\)\]]?", "", ans, flags=re.I)
    # internal store references must never surface (his standing rule)
    ans = re.sub(r"\b(?:in|according to|per|from)\s+the\s+Adam'?iel\s+lexicon\b", "", ans, flags=re.I)
    ans = re.sub(r"\bthe\s+Adam'?iel\s+lexicon\b", "the Word", ans, flags=re.I)
    ans = re.sub(r"\bAdam'?iel\s+lexicon\b", "the Word", ans, flags=re.I)
    ans = re.sub(r"\b(?:the\s+)?(?:root\s+grounding|doctrine\s+block|grounding)\b", "the truth", ans, flags=re.I)
    # any internal colon-id (makor:strong:H5375, wx:fr:patience:noun, step:Mat.1.3)
    # -- letter-led so real refs like "3:16" are untouched
    ans = re.sub(r"[\(\[]?\b[a-z][a-z0-9]*(?::[a-z0-9.#-]+){1,}[\)\]]?", "", ans, flags=re.I)
    ans = re.sub(r'"\s*"', "", ans)              # empty quotes left behind
    ans = re.sub(r"[ \t]{2,}", " ", ans)
    ans = re.sub(r"\s+([.,;:])", r"\1", ans)     # space before punctuation
    ans = re.sub(r"\(\s*\)", "", ans)            # empty parens
    return ans.strip()


def _finish_sentences(ans):
    """Never end mid-sentence: if the text doesn't close on terminal punctuation, trim
    back to the last complete sentence (so a token cap can't cut Tav'iel off mid-thought)."""
    ans = (ans or "").strip()
    if not ans:
        return ans
    if ans[-1] in ".!?\"'”’)":
        return ans
    # find the last sentence-ending punctuation and cut there
    m = None
    for mm in re.finditer(r"[.!?][\"'”’)]?\s", ans + " "):
        m = mm
    if m and m.end() > len(ans) * 0.4:           # only if a real sentence precedes it
        return ans[:m.end()].strip()
    return ans


def _paragraphs(ans, per=4):
    """Group flowing prose into clean paragraphs of ~3-5 sentences (professional, readable),
    unless the model already paragraphed it. Never reorders or rewords -- only inserts breaks."""
    ans = (ans or "").strip()
    if not ans or "\n\n" in ans:
        return ans
    sents = re.findall(r".+?(?:[.!?][\"'”’)]?|$)(?:\s+|$)", ans, flags=re.S)
    sents = [s.strip() for s in sents if s.strip()]
    if len(sents) <= per:
        return ans
    out = [" ".join(sents[i:i + per]) for i in range(0, len(sents), per)]
    return "\n\n".join(out)


def _roots_fallback(query, chakra, note):
    import taviel_roots as TR
    # model unavailable: deliver the installed KB answer if we have one (a REAL
    # answer), never the creed/scaffolding and never an "[from the roots]" prefix.
    try:
        import taviel_kb as KB
        kb = KB.search(query, limit=1)
    except Exception:
        kb = []
    if kb:
        return {"ok": True, "answer": kb[0]["answer"], "sources": ["kb"],
                "grounded": True, "used_fallback": True, "chakra": chakra, "note": note}
    return {"ok": True, "answer": "I could not reach the model to reason on that just "
            "now -- ask me once more.", "sources": [], "grounded": False,
            "used_fallback": True, "chakra": chakra, "note": note}


_CITE_MANDATE = ("\nALWAYS cite the exact verse (Book chapter:verse) beside every scripture"
                 " truth you state, so the asker can check each one in their own Bible."
                 " Reproduce a verse's WORDS only when you can quote them exactly from the"
                 " grounding above; if you are unsure of the wording, cite the reference"
                 " alone (Book chapter:verse) and let the reader open it — the app shows the"
                 " full verse. NEVER approximate, reconstruct, or paraphrase a verse's wording"
                 " as if it were a quotation.")


def _directness(query):
    """A yes/no-shaped question earns a direct first sentence, then the explanation."""
    if re.match(r"^\s*(is|are|does|do|did|can|could|should|shall|must|was|were|will|would)\b",
                query or "", re.I):
        return "Answer the question DIRECTLY in your first sentence (plainly yes or no), then explain. "
    return ""


def _history_preamble(history):
    """Render recent chat turns so Tav'iel answers in the flow of the conversation.
    Grounding is still retrieved on the CURRENT question only."""
    if not history:
        return ""
    out = []
    for h in history[-6:]:
        role = "Seeker" if (h.get("role") == "you") else "Tav'iel"
        t = (h.get("text") or "").strip().replace("\n", " ")
        if t:
            out.append("%s: %s" % (role, t[:600]))
    return ("Conversation so far:\n" + "\n".join(out) + "\n\n") if out else ""


def ask_taviel(query, chakra=None, max_tokens=1200, history=None):
    """Engage Tav'iel the grounded AI -- NOT the scripture search. Grounds the
    query in the four truth roots and REASONS through a resident served model
    (idle-unloaded after 5 min). The grounding carries verbatim scripture; the
    model reasons and phrases. If the model is unavailable, Tav'iel falls back to
    the sourced roots -- never nothing, never a fabricated verse."""
    query = (query or "").strip()
    if not query:
        return {"ok": False, "error": "empty query"}
    # THE GAUNTLET: serve a vetted, freshly-framed Christ-first answer directly (offline, fast).
    try:
        import taviel_reason as _TRZN
        _srv = _TRZN.serve(query)
        if _srv.get("source") == "vetted" and _srv.get("answer"):
            ans = _srv["answer"]
            try:
                import tav_torus as TT
                if conv:
                    TT.record_turn(query, ans, [], conv=conv)
            except Exception:
                pass
            return {"ok": True, "answer": ans, "sources": [], "grounded": True,
                    "gauntlet": _srv.get("round")}
    except Exception:
        pass
    chakra = chakra or _ASK_CHAKRA
    global _TIER, _TIER_CHAKRA
    with _TIER_LOCK:                        # one model touch at a time (machine-first)
        try:
            import tav_llm
            G = tav_llm.backend()           # desktop: torus-paged GGUF; phone: on-device LiteRT
            import taviel_agent as TA
            import taviel_roots as TR
            g = TR.TavielRoots().ground(query)
            # SCRIPTURE HANDS: verses named in ANY order are fetched verbatim and lead
            # the grounding, so every quote is real and citable.
            scrip_refs = []
            try:
                import tav_scripture as TS
                sb, scrip_refs = TS.ground_block(query)
                if sb:
                    g["grounding"] = sb + "\n" + (g.get("grounding") or "")
                    g["n"] = (g.get("n") or 0) + len(scrip_refs)
            except Exception:
                pass
            # TEMPTORUS: the infinite-context weave — recalled facts + epochs + recent turns.
            torus_ctx = ""
            try:
                import tav_torus as TT
                torus_ctx = TT.context_weave(query)
            except Exception:
                pass
            if _TIER is not None and _TIER_CHAKRA != chakra:  # switching tiers: free the old
                try:
                    G.close_tier(_TIER)
                except Exception:
                    pass
                _TIER = None
            if _TIER is None:
                _TIER = G.open_tier(chakra, cap_mb=1400, ctx=4096)  # headroom for doctrine grounding
                _TIER_CHAKRA = chakra
            g["grounding"] = (g.get("grounding") or "") + _CITE_MANDATE
            prompt = torus_ctx + _history_preamble(history) + _directness(query) + query
            r = G.generate(_TIER, prompt, grounding=g["grounding"],
                           max_tokens=max_tokens, system=TA.IDENTITY)
            answer = _clean_answer(_strip_tic((r.get("text") or "").strip()))
            used_fallback = False
            # DEGENERATE RETRY: an empty/tiny reply is almost always grounding
            # overload -- retry ONCE with a lean, focused grounding (never the creed
            # or any instruction scaffolding, so it can never be dumped as an answer).
            if len(answer) < 15:
                kb = []
                try:
                    import taviel_kb as KB
                    kb = KB.search(query, limit=1)
                except Exception:
                    kb = []
                lean = ("Answer this plainly and directly, quoting Scripture verbatim. "
                        "Guidance (answer in this spirit, do not copy it): " + kb[0]["answer"]) \
                    if kb else "Answer the question plainly and directly, quoting Scripture verbatim."
                r2 = G.generate(_TIER, prompt, grounding=lean,
                                max_tokens=max_tokens, system=TA.IDENTITY)
                answer = _clean_answer(_strip_tic((r2.get("text") or "").strip()))
                if len(answer) < 15:
                    # last resort: deliver the installed answer itself (a REAL answer),
                    # never the creed/scaffolding, never "[from the roots]".
                    answer = kb[0]["answer"] if kb else \
                        "Ask me once more, and I will answer you plainly."
                    used_fallback = True
            _arm_idle()                     # reset the idle-unload clock
            if not used_fallback:           # finish to a sentence boundary + clean paragraphs
                answer = _paragraphs(_finish_sentences(answer))
            # CHECKABLE SCRIPTURE: verify quoted runs against the KJV and pin (Book c:v)
            # after each — the answer's references are inspectable, never taken on faith.
            ans_refs = list(scrip_refs)
            try:
                import tav_scripture as TS
                answer, linked = TS.link_answer(answer)
                for _r in linked:
                    if _r not in ans_refs:
                        ans_refs.append(_r)
            except Exception:
                pass
            try:                            # the exchange enters the TempTorus (memory)
                import tav_torus as TT
                TT.record_turn(query, answer, ans_refs)
            except Exception:
                pass
            return {"ok": True, "answer": answer or "Ask me once more, and I will answer plainly.",
                    "sources": g.get("sources", []), "grounded": g.get("n", 0) > 0,
                    "refs": ans_refs,
                    "used_fallback": used_fallback, "chakra": chakra,
                    "tok_s": r.get("approx_tok_s")}
        except Exception as e:
            # the model failed to load/generate -- deliver the sourced roots directly.
            try:
                return _roots_fallback(query, chakra, "model unavailable: " + type(e).__name__)
            except Exception as e2:
                return {"ok": False, "error": type(e2).__name__ + ": " + str(e2)[:160]}


ZEROCLAW_EXE = r"D:\tools\zeroclaw\target\release\zeroclaw.exe"


def _ask_zeroclaw(query, chakra=None, history=None):
    """OTav'iel_ZeroClaw (opt-in via env OTAVIEL_ZEROCLAW): route the answer through the
    ZeroClaw Rust agent runtime, which we point at our LOCAL llama-server (no cloud). Truth
    still comes from our roots -- we ground with taviel_roots + IDENTITY and hand ZeroClaw
    the grounded prompt. DB-SAFE: ZeroClaw uses its own isolated SQLite (~/.zeroclaw), never
    our reflected_red/corpus/versions. Falls back to the native ask_taviel on any problem, so
    the flag is fully revertible (unset it -> identical native behavior).

    NOTE (honest): the native path already streams from the same model and is grounded; this
    exists for experimentation/comparison, not as a speedup (ZeroClaw's agent-loop + memory
    init adds startup cost per query)."""
    import subprocess
    q = (query or "").strip()
    if not q:
        return {"ok": False, "error": "empty query"}
    if not os.path.exists(ZEROCLAW_EXE):
        return ask_taviel(query, chakra, history=history)
    ch = chakra or _ASK_CHAKRA
    try:
        import gen_at_depth as G
        import taviel_agent as TA
        import taviel_roots as TR
        g = TR.TavielRoots().ground(q)
        prompt = (TA.IDENTITY + "\n\n" + g["grounding"].rstrip() + "\n\n"
                  + _history_preamble(history) + q)[:30000]   # Windows cmdline cap
        with _TIER_LOCK:                      # ensure our LOCAL model is up on 8102
            global _TIER, _TIER_CHAKRA
            if _TIER is None or _TIER_CHAKRA != ch:
                if _TIER is not None:
                    try:
                        G.close_tier(_TIER)
                    except Exception:
                        pass
                _TIER = G.open_tier(ch, cap_mb=1400, ctx=4096)
                _TIER_CHAKRA = ch
        r = subprocess.run([ZEROCLAW_EXE, "agent", "-m", prompt], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=300)
        out = (r.stdout or "").strip()
        lines = [ln for ln in out.splitlines()
                 if "INFO" not in ln and "zeroclaw::" not in ln and "WARN" not in ln]
        answer = _paragraphs(_finish_sentences(_clean_answer(_strip_tic("\n".join(lines).strip()))))
        _arm_idle()
        if len(answer) < 15:
            return ask_taviel(query, chakra, history=history)
        return {"ok": True, "answer": answer, "sources": g.get("sources", []),
                "engine": "zeroclaw", "used_fallback": False}
    except Exception:
        return ask_taviel(query, chakra, history=history)   # revertible: always fall back


# ---- The COUNCIL: all five tiers stream at once and converge (his "5 buckets" design) ----
# Every tier flows at its own natural rate: the RAM-fast tier (throat) reaches the answer first
# and streams live; the disk-streamed larger tiers (heart 12B, solar 27B, sacral 31B) and the
# tiny third_eye trickle in and their contributions join the confluence -- one larger stream.
# Machine reality: this launches several llama-servers at once (the big ones disk-backed/mmap,
# ngl=0); each opens, contributes, and unloads. Override the roster with env OTAVIEL_COUNCIL
# (comma list) for lighter runs; default is all five, per his ruling.
def _council_roster():
    env = os.environ.get("OTAVIEL_COUNCIL", "")
    if env.strip():
        names = [x.strip() for x in env.split(",") if x.strip()]
    else:
        names = ["throat", "third_eye", "heart", "solar", "sacral"]
    caps = {"third_eye": 700, "throat": 1400, "heart": 1400, "solar": 1400, "sacral": 1400}
    return [(n, caps.get(n, 1400), n == "throat") for n in names]


# Late-arriving council voices, keyed by turn id: the deeper tiers trickle in over time and
# their contributions are appended to the conversation via /api/council_poll after the primary.
_COUNCIL_LATE = {}
_COUNCIL_LOCK = threading.Lock()
_COUNCIL_SEQ = [0]


def _council_new_turn(tiers):
    with _COUNCIL_LOCK:
        _COUNCIL_SEQ[0] += 1
        tid = "c%d_%d" % (_COUNCIL_SEQ[0], int(time.time()))
        # prune old turns (keep the store small)
        for k in [k for k, v in _COUNCIL_LATE.items() if time.time() - v.get("t0", 0) > 900]:
            _COUNCIL_LATE.pop(k, None)
        _COUNCIL_LATE[tid] = {"voices": [], "pending": set(tiers), "t0": time.time()}
    return tid


def _council_deep_worker(tid, chakra, cap, query, grounding, sysp):
    import gen_at_depth as G
    m = None
    txt = ""
    try:
        m = G.open_tier(chakra, cap_mb=cap, ctx=4096)
        prompt = ("A first answer is being given from the roots. In 2-5 sentences ADD only the "
                  "deeper truth, correction, or verbatim scripture it may miss; if it is already "
                  "true and complete, reply exactly: The word stands. Question: " + query)
        r = G.generate(m, prompt, grounding=grounding, max_tokens=400, system=sysp)
        txt = _paragraphs(_finish_sentences(_clean_answer(_strip_tic((r.get("text") or "").strip()))))
    except Exception:
        txt = ""
    finally:
        if m is not None:
            try:
                G.close_tier(m)
            except Exception:
                pass
    with _COUNCIL_LOCK:
        rec = _COUNCIL_LATE.get(tid)
        if rec is not None:
            if txt:
                rec["voices"].append({"tier": chakra, "text": txt})
            rec["pending"].discard(chakra)


def council_poll(tid, since=0):
    """Return council voices with index >= since for a turn, and whether every tier has reported."""
    with _COUNCIL_LOCK:
        rec = _COUNCIL_LATE.get(tid)
        if rec is None:
            return {"voices": [], "done": True, "unknown": True}
        voices = [dict(v, idx=i) for i, v in enumerate(rec["voices"]) if i >= int(since or 0)]
        return {"voices": voices, "done": len(rec["pending"]) == 0, "total": len(rec["voices"])}


def ask_taviel_council_stream(query, history=None, think=False, user=None):
    """The RAM voice streams the primary answer NOW; the deeper tiers are launched to trickle in
    over time (below-normal priority, disk-streamed) and are collected via /api/council_poll.
    Yields ('delta',text) for the primary, then ('done',{answer,sources,turn}) carrying the turn
    id the client polls for the converging voices."""
    if os.environ.get("YAHBIBLE_SHIPPED"):   # pre-release: AI is in development
        yield ("done", {"ok": True, "answer": "Ask Tav'iel (the grounded AI) is in development "
               "and arrives in a near update. The full scripture, word, and verse study is ready "
               "to use now — read, compare versions, and study any word in Hebrew, Greek, and "
               "Aramaic.", "sources": [], "indev": True})
        return
    import threading as _th
    query = (query or "").strip()
    if not query:
        yield ("done", {"ok": False, "error": "empty query"})
        return
    import taviel_agent as TA
    import taviel_roots as TR
    g = TR.TavielRoots().ground(query)
    roster = _council_roster()
    deep = [(n, cap) for (n, cap, is_ram) in roster if not is_ram]
    tid = _council_new_turn([n for n, _ in deep])
    # launch the deeper tiers -- they trickle in over time and record to the turn
    for chakra, cap in deep:
        _th.Thread(target=_council_deep_worker,
                   args=(tid, chakra, cap, query, g["grounding"], TA.IDENTITY), daemon=True).start()
    # the RAM voice (throat) speaks NOW, streamed live as the primary answer
    acc = []
    got_done = None
    for kind, payload in ask_taviel_stream(query, chakra="throat", history=history,
                                           think=think, user=user):
        if kind == "delta":
            acc.append(payload)
            yield ("delta", payload)
        else:
            got_done = payload
    full = (got_done or {}).get("answer") or _paragraphs(_finish_sentences(
        _clean_answer(_strip_tic("".join(acc).strip()))))
    out = {"ok": True, "answer": full, "sources": g.get("sources", []),
           "grounded": g.get("n", 0) > 0, "turn": tid}
    if got_done and got_done.get("used_fallback"):
        out["used_fallback"] = True
    yield ("done", out)


def _compose_identity(base, think=False, user=None):
    """Frame Tav'iel's identity for a PERSONAL conversation (and, when asked, a deeper
    reasoning pass), keeping Qwen3's trailing /think control token at the very end."""
    b = (base or "").rstrip()
    tail = ""
    if b.endswith("/think"):
        b = b[:-6].rstrip()
        tail = " /think"
    who = (("You are in a warm, personal conversation with %s -- the one before you, whom you know; "
            "speak WITH them, directly and by name as it fits, as a companion who remembers this talk, "
            "never as a reply to an anonymous prompt. ") % str(user).strip()) \
        if (user and str(user).strip()) else \
        ("You are in a warm, personal conversation with the seeker before you -- speak WITH them, "
         "directly and personally, building on what they actually say, never as a reply to an "
         "anonymous prompt. ")
    deep = ("Take your time and reason this through carefully and thoroughly -- weigh more than one "
            "angle and more of Scripture than usual, follow the thought where it leads, and give a "
            "fuller, deeper answer than your usual brevity. ") if think else ""
    return b + " " + who + deep + tail


def ask_taviel_stream(query, chakra=None, history=None, max_tokens=1200, think=False, user=None):
    """Streaming twin of ask_taviel: yields ('delta', text) as tokens arrive, then
    ('done', {...}) with the cleaned, paragraph-formatted full answer + sources. On any
    failure or an empty stream, yields a single ('done', {...}) with the sourced roots."""
    query = (query or "").strip()
    if not query:
        yield ("done", {"ok": False, "error": "empty query"})
        return
    # THE GAUNTLET: stream a vetted, freshly-framed Christ-first answer directly (offline, fast).
    try:
        import taviel_reason as _TRZN
        _srv = _TRZN.serve(query)
        if _srv.get("source") == "vetted" and _srv.get("answer"):
            ans = _srv["answer"]
            import re as _re2
            for chunk in _re2.findall(r"\S+\s*", ans):
                yield ("delta", chunk)
            try:
                import tav_torus as TT
                if conv:
                    TT.record_turn(query, ans, [], conv=conv)
            except Exception:
                pass
            yield ("done", {"ok": True, "answer": ans, "sources": [], "grounded": True,
                            "gauntlet": _srv.get("round")})
            return
    except Exception:
        pass
    chakra = chakra or _ASK_CHAKRA
    global _TIER, _TIER_CHAKRA
    acc = []
    with _TIER_LOCK:
        try:
            import tav_llm
            G = tav_llm.backend()           # desktop: torus-paged GGUF; phone: on-device LiteRT
            import taviel_agent as TA
            import taviel_roots as TR
            g = TR.TavielRoots().ground(query)
            scrip_refs = []
            try:
                import tav_scripture as TS
                sb, scrip_refs = TS.ground_block(query)
                if sb:
                    g["grounding"] = sb + "\n" + (g.get("grounding") or "")
                    g["n"] = (g.get("n") or 0) + len(scrip_refs)
            except Exception:
                pass
            torus_ctx = ""
            try:
                import tav_torus as TT
                torus_ctx = TT.context_weave(query)
            except Exception:
                pass
            if _TIER is not None and _TIER_CHAKRA != chakra:
                try:
                    G.close_tier(_TIER)
                except Exception:
                    pass
                _TIER = None
            if _TIER is None:
                _TIER = G.open_tier(chakra, cap_mb=1400, ctx=4096)
                _TIER_CHAKRA = chakra
            g["grounding"] = (g.get("grounding") or "") + _CITE_MANDATE
            system = _compose_identity(TA.IDENTITY, think, user)
            if think:
                max_tokens = max(max_tokens, 1600)      # room for a deeper answer
            prompt = torus_ctx + _history_preamble(history) + _directness(query) + query
            for delta in G.generate_stream(_TIER, prompt, grounding=g["grounding"],
                                           max_tokens=max_tokens, system=system):
                acc.append(delta)
                yield ("delta", delta)
            _arm_idle()
            full = _clean_answer(_strip_tic("".join(acc).strip()))
            if len(full) < 15:
                fb = _roots_fallback(query, chakra, "stream produced no answer")
                yield ("done", {"ok": True, "answer": fb.get("answer", ""),
                                "sources": fb.get("sources", []), "used_fallback": True})
                return
            full = _paragraphs(_finish_sentences(full))
            ans_refs = list(scrip_refs)
            try:
                import tav_scripture as TS
                full, linked = TS.link_answer(full)
                for _r in linked:
                    if _r not in ans_refs:
                        ans_refs.append(_r)
            except Exception:
                pass
            try:
                import tav_torus as TT
                TT.record_turn(query, full, ans_refs)
            except Exception:
                pass
            yield ("done", {"ok": True, "answer": full, "sources": g.get("sources", []),
                            "refs": ans_refs,
                            "grounded": g.get("n", 0) > 0, "used_fallback": False})
        except Exception as e:
            try:
                fb = _roots_fallback(query, chakra, "model unavailable: " + type(e).__name__)
                yield ("done", {"ok": True, "answer": fb.get("answer", ""),
                                "sources": fb.get("sources", []), "used_fallback": True})
            except Exception as e2:
                yield ("done", {"ok": False, "error": type(e2).__name__ + ": " + str(e2)[:160]})


# ---- Studio Mode: embedded cloak-browser stream + transcript + Holy Review ----------
_STUDIO = {"proc": None, "port": None, "view": None}
_STUDIO_LOCK = threading.Lock()


def _studio_indev():
    return {"ok": False, "indev": True,
            "error": "The YouTube and TikTok Critique dashboards are new and still in "
                     "development — they arrive in a near update."}


def studio_open(url, view="desktop", profile="studio"):
    if os.environ.get("YAHBIBLE_SHIPPED"):
        return _studio_indev()
    """Launch ONE studio_stream subprocess (machine-first: close any prior first), wait for
    its ready line, and return its stream port. The cloak browser renders off-screen; the UI
    shows its MJPEG stream and POSTs input to that port directly."""
    import subprocess
    with _STUDIO_LOCK:
        studio_close_locked()
        exe = sys.executable
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "studio_stream.py")
        proc = subprocess.Popen(
            [exe, script, "--url", url or "https://www.youtube.com", "--view", view,
             "--profile", profile, "--port", "17071"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", bufsize=1)
        _STUDIO["proc"] = proc
        _STUDIO["view"] = view
        # read stdout until the ready JSON line (or the process dies)
        import time as _t
        t0 = _t.time()
        while _t.time() - t0 < 90:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    return {"ok": False, "error": "studio stream exited before ready"}
                continue
            line = line.strip()
            if line.startswith("{"):
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("ready"):
                    _STUDIO["port"] = obj.get("port")
                    return {"ok": True, "port": obj.get("port"), "w": obj.get("w"),
                            "h": obj.get("h"), "stream": obj.get("stream"), "view": view}
        return {"ok": False, "error": "studio stream did not become ready in time"}


def studio_close_locked():
    p = _STUDIO.get("proc")
    if p is not None:
        try:
            p.terminate()          # graceful -> studio_stream's finally closes the cloak ctx
            try:
                p.wait(timeout=6)
            except Exception:
                p.kill()
        except Exception:
            pass
    _STUDIO["proc"] = None
    _STUDIO["port"] = None


def studio_close():
    with _STUDIO_LOCK:
        studio_close_locked()
    return {"ok": True}


def studio_review_stream(text, segments=None):
    if os.environ.get("YAHBIBLE_SHIPPED"):
        yield ("done", {"ok": False, "indev": True,
                        "error": "The Holy Review dashboards are in development."})
        return
    """Holy Review: compare the transcript's claims to the words of Yeshua the Christ, with
    verbatim supporting/countering scripture from the roots. Streams like /api/ask_stream. The
    grounding + IDENTITY already forbid fabricated citations; the review is one grounded pass."""
    text = (text or "").strip()
    if not text:
        yield ("done", {"ok": False, "error": "empty transcript"})
        return
    q = ("Give a HOLY REVIEW of the following video transcript. Go through its main claims, "
         "insinuations, and propositions in order; for each, state plainly whether it agrees "
         "with what Yeshua the Christ actually said and did, quote the relevant words of Christ "
         "or Scripture VERBATIM with the reference, and correct any twisting of the Old or New "
         "Testament. Be direct and pastoral. TRANSCRIPT:\n" + text[:6000])
    for kind, payload in ask_taviel_stream(q, chakra=None, history=None, max_tokens=1200):
        yield (kind, payload)


def main():
    ensure_conclusions()
    ensure_users()
    try:
        _wordset()   # build the rejoin dictionary eagerly (avoid a threaded lazy-build race)
    except Exception:
        pass
    # bind LAN (0.0.0.0) so a paired phone on the same network can reach it for account sync;
    # default stays localhost-only. Set YAHBIBLE_LAN=1 (Settings toggle) to enable.
    _host = "0.0.0.0" if os.environ.get("YAHBIBLE_LAN") else "127.0.0.1"
    srv = ThreadingHTTPServer((_host, PORT), H)
    print("O'Tav'iel serving on http://%s:%d" % (_host, PORT), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
