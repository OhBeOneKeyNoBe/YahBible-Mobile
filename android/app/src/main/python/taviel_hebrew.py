#!/usr/bin/env python3
r"""In-depth HEBREW study for every name in the Gnostic Lineage. Given a name, returns its
most-likely Hebrew spelling, transliteration, meaning, and a letter-by-letter dissection
(each Hebrew letter's pictographic name, meaning, and gematria value), plus the gematria
total. Names that are Greek/Coptic/invented (Barbelo, Harmozel, Autogenes...) are honestly
marked as PHONETIC transliterations, not native Hebrew words; genuine Hebrew names (Adam,
Sabaoth, Seth...) are marked direct. The per-name spellings live in taviel_hebrew_names.json
(authored separately); this module generates the dissection from the spelling."""
import json
import os

# glyph -> (letter-name, pictographic meaning, standard gematria value). Finals fold to base.
ALEPHBET = {
    "א": ("Aleph", "ox — strength, the leader, the One", 1),
    "ב": ("Bet", "house, tent, dwelling, within", 2),
    "ג": ("Gimel", "camel — to lift up, pride, recompense", 3),
    "ד": ("Dalet", "door — pathway, to enter, movement", 4),
    "ה": ("He", "window, breath — to reveal, behold, the divine breath", 5),
    "ו": ("Vav", "nail, hook — to join, 'and', the connecting peg", 6),
    "ז": ("Zayin", "weapon, sword — to cut, to nourish, a cutting", 7),
    "ח": ("Het", "fence, wall — to separate, protect; life (chai)", 8),
    "ט": ("Tet", "basket, coiled serpent — to surround; good (tov)", 9),
    "י": ("Yod", "hand, arm, deed — the work of the hand, the smallest letter", 10),
    "כ": ("Kaf", "open palm — to cover, to bend, to allow", 20),
    "ך": ("Kaf (final)", "open palm — to cover (word-final form)", 20),
    "ל": ("Lamed", "shepherd's staff, goad — to teach, to urge toward, authority", 30),
    "מ": ("Mem", "water — chaos, the deep, the hidden, mighty", 40),
    "ם": ("Mem (final)", "water — the sealed/closed deep (word-final form)", 40),
    "נ": ("Nun", "fish, seed — life, continuation, the heir", 50),
    "ן": ("Nun (final)", "fish, seed — life continued (word-final form)", 50),
    "ס": ("Samekh", "prop, support — to uphold, to lean on, the turning", 60),
    "ע": ("Ayin", "eye, fountain — to see, to know, insight", 70),
    "פ": ("Pe", "mouth — the word, to speak, an opening", 80),
    "ף": ("Pe (final)", "mouth — the spoken word (word-final form)", 80),
    "צ": ("Tsadi", "fish-hook, trail — the righteous one, to pull toward, desire", 90),
    "ץ": ("Tsadi (final)", "the righteous one (word-final form)", 90),
    "ק": ("Qof", "back of the head, horizon — the least, behind, to encircle, holiness", 100),
    "ר": ("Resh", "head of a man — the highest, chief, a person, beginning", 200),
    "ש": ("Shin", "teeth — to consume, to press, fire; the divine Name letter", 300),
    "ת": ("Tav", "mark, sign, cross — covenant, the seal, completion (the final letter)", 400),
}
# niqqud / cantillation stripped so the dissection reads only the consonantal letters
_STRIP = set("ְֱֲֳִֵֶַָֹֺֻ"
             "ׇּֽֿׁׂ־׀׃‎‏")

_NAMES = None
_VARIDX = None
_HERE = os.path.dirname(os.path.abspath(__file__))
_JSON = os.path.join(_HERE, "taviel_hebrew_names.json")           # gnostic lineage names
_JSON_BIBLE = os.path.join(_HERE, "taviel_hebrew_bible.json")     # biblical lineage names
_JSON_BOOKS = os.path.join(_HERE, "taviel_hebrew_books.json")     # book / scripture titles
_JSON_COMMON = os.path.join(_HERE, "taviel_hebrew_common.json")   # common words -> canonical Hebrew
_JSON_ENOCH = os.path.join(_HERE, "taviel_enoch_full.json")       # Enoch angels/terms (def+hebrew)
_JSON_ENOCH_SUPP = os.path.join(_HERE, "taviel_enoch_supp.json")  # supplement: permutations + real terms
_JSON_ENOCH_NAMES = os.path.join(_HERE, "taviel_enoch_names.json") # Watchers / luminaries / kin names


import re


def _norm(name):
    """Core lookup key: lowercase, drop parentheticals and a leading 'the'."""
    s = re.sub(r"\([^)]*\)", "", name or "").lower().strip()
    s = re.sub(r"^the\s+", "", s).strip()
    return s


_STRONGS_REV = None
_STRONGS_PATH = os.path.join(_HERE, "taviel_strongs.json")


def _strongs_rev():
    """Reverse index English word -> the Hebrew word the KJV renders it from (Strong's), so an
    ordinary word like 'blessed' still gets a Hebrew deep-dive. Prefers the most specific entry
    (shortest KJV-rendering list) for each word."""
    global _STRONGS_REV
    if _STRONGS_REV is None:
        _STRONGS_REV = {}
        best = {}
        try:
            j = json.load(open(_STRONGS_PATH, encoding="utf-8"))
            for k, e in j.items():
                if not k.startswith("H"):
                    continue
                heb = e.get("lemma")
                if not heb:
                    continue
                kjv = e.get("kjv", "") or ""
                words = re.findall(r"[A-Za-z]+", kjv)
                # skip entries that are a lone proper noun (e.g. 'Nahum.') so common words
                # don't map onto an obscure name
                stripped = kjv.strip().rstrip(".")
                if len(words) == 1 and stripped[:1].isupper():
                    continue
                n = len(words)
                for idx, w in enumerate(words):
                    lw = w.lower()
                    if len(lw) < 3:
                        continue
                    # rank: prefer the target appearing EARLY (primary sense), then a short list
                    score = idx * 3 + n
                    if lw not in best or score < best[lw]:
                        best[lw] = score
                        _STRONGS_REV[lw] = (heb, e.get("x") or "", k, kjv)
        except Exception:
            pass
    return _STRONGS_REV


_TL_DIGRAPHS = [("tsch", "טש"), ("sch", "שׁ"), ("tch", "טש"), ("sh", "שׁ"), ("ch", "ח"),
                ("ts", "צ"), ("tz", "צ"), ("th", "ת"), ("ph", "פ"), ("kh", "כ"),
                ("ck", "ק"), ("qu", "קְו"), ("wh", "ו")]
_TL_SINGLE = {"a": "", "b": "ב", "c": "ק", "d": "ד", "e": "", "f": "פ", "g": "ג", "h": "ה",
              "i": "י", "j": "י", "k": "ק", "l": "ל", "m": "מ", "n": "נ", "o": "ו", "p": "פ",
              "q": "ק", "r": "ר", "s": "ס", "t": "ת", "u": "ו", "v": "ו", "w": "ו", "x": "קס",
              "y": "י", "z": "ז"}
_TL_FINAL = {"כ": "ך", "מ": "ם", "נ": "ן", "פ": "ף", "צ": "ץ"}


_ARABIC = {
    "ا": "a", "ب": "b", "ت": "t", "ث": "th", "ج": "j", "ح": "h",
    "خ": "kh", "د": "d", "ذ": "dh", "ر": "r", "ز": "z", "س": "s",
    "ش": "sh", "ص": "s", "ض": "d", "ط": "t", "ظ": "z", "ع": "'",
    "غ": "gh", "ف": "f", "ق": "q", "ك": "k", "ل": "l", "م": "m",
    "ن": "n", "ه": "h", "و": "w", "ي": "y", "ة": "h", "ى": "a",
    "ء": "'", "أ": "a", "إ": "i", "آ": "a", "ؤ": "w", "ئ": "y",
    "ٰ": "a", "َ": "a", "ُ": "u", "ِ": "i", "ً": "an", "ٌ": "un",
    "ٍ": "in", "ّ": "", "ْ": "",
}


def _has_arabic(s):
    return any("؀" <= c <= "ۿ" for c in (s or ""))


def _has_hebrew(s):
    return any("א" <= c <= "ת" for c in (s or "")) or any(c in _HEB_FINALS for c in (s or ""))


_HEB_FINALS = {"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"}
_HEB_ROM = {"א": "'", "ב": "b", "ג": "g", "ד": "d", "ה": "h", "ו": "v", "ז": "z", "ח": "ch",
            "ט": "t", "י": "y", "כ": "k", "ל": "l", "מ": "m", "נ": "n", "ס": "s", "ע": "'",
            "פ": "p", "צ": "ts", "ק": "q", "ר": "r", "ש": "sh", "ת": "t"}


def ar_romanize(word):
    """Best-effort romanization of an Arabic word -> Latin, so it can then be written in
    Hebrew letters by sound (per the always-create rule: any word gets a Hebrew deep-dive)."""
    out = []
    for c in (word or ""):
        if c in _ARABIC:
            out.append(_ARABIC[c])
        elif c.isspace():
            out.append(" ")
    return "".join(out)


def transliterate(word):
    """Write ANY word's sound in Hebrew consonant-letters, so every word gets a letter-study
    even when no lexical Hebrew equivalent exists (e.g. a foreign name)."""
    w = re.sub(r"[^a-z]", "", (word or "").lower())
    out, i = [], 0
    while i < len(w):
        hit = None
        for dg, heb in _TL_DIGRAPHS:
            if w.startswith(dg, i):
                hit = (heb, len(dg)); break
        if hit:
            out.append(hit[0]); i += hit[1]
        else:
            out.append(_TL_SINGLE.get(w[i], "")); i += 1
    heb = "".join(out)
    # all-vowel words (e.g. "a", "e", "ea") drop to nothing in consonantal writing -- carry the
    # vowels with matres lectionis so EVERY word still gets a Hebrew form (never empty).
    if not heb:
        _VOW = {"a": "א", "e": "א", "i": "י", "o": "ו", "u": "ו", "y": "י"}
        heb = "".join(_VOW.get(ch, "") for ch in w) or "א"
    # give the last consonant its word-final form
    m = re.search(r"[א-ת]$", heb)
    if m and heb[-1] in _TL_FINAL:
        heb = heb[:-1] + _TL_FINAL[heb[-1]]
    return heb


def _variant_key(w):
    """Fuzzy consonant skeleton so alternative transliterations collide (Yeshiba~Yeshivah)."""
    s = re.sub(r"[^a-z]", "", (w or "").lower())
    if len(s) < 3:
        return ""
    s = s.replace("ph", "f").replace("th", "t").replace("sh", "S").replace("ch", "K")
    s = s.translate(str.maketrans({"v": "b", "w": "b", "k": "K", "q": "K", "c": "K",
                                   "z": "s", "x": "s", "j": "y"}))
    s = s.replace("h", "")
    if not s:                       # e.g. all-'h' junk ("hhh") -> no skeleton
        return ""
    head, rest = s[0], re.sub(r"[aeiouy]", "", s[1:])
    return re.sub(r"(.)\1+", r"\1", head + rest)


def _load():
    global _NAMES, _VARIDX
    if _NAMES is None:
        m, vi = {}, {}
        for path in (_JSON, _JSON_BIBLE, _JSON_BOOKS, _JSON_COMMON):   # names + titles + common words
            try:
                for k, v in json.load(open(path, encoding="utf-8")).items():
                    m[_norm(k)] = v
            except Exception:
                pass
        for ep in (_JSON_ENOCH, _JSON_ENOCH_SUPP, _JSON_ENOCH_NAMES):   # Enoch terms: def -> meaning
            try:
                for k, v in json.load(open(ep, encoding="utf-8")).items():
                    if v.get("hebrew"):
                        m.setdefault(_norm(k), {"hebrew": v.get("hebrew", ""),
                                                "translit": v.get("translit", ""),
                                                "meaning": v.get("def", ""), "direct": True})
            except Exception:
                pass
        for k, v in m.items():
            vk = _variant_key(k)
            if vk:
                vi.setdefault(vk, k)
        _NAMES, _VARIDX = m, vi
    return _NAMES


def dissect(hebrew):
    """Letter-by-letter dissection of a Hebrew string, with a gematria total."""
    letters, total = [], 0
    for ch in hebrew:
        if ch in _STRIP or ch.isspace():
            continue
        info = ALEPHBET.get(ch)
        if not info:
            continue
        name, meaning, val = info
        letters.append({"glyph": ch, "name": name, "meaning": meaning, "value": val})
        total += val
    return letters, total


_ALIASES = None


def _alias(w):
    global _ALIASES
    if _ALIASES is None:
        try:
            _ALIASES = {k.lower(): v.lower() for k, v in json.load(
                open(os.path.join(_HERE, "taviel_aliases.json"), encoding="utf-8")).items()}
        except Exception:
            _ALIASES = {}
    return _ALIASES.get(w, w)


def study(name):
    """Return the Hebrew study for a name, or None if we have no spelling for it.
    Applies spelling aliases (Tsivan->Sivan) and a variant-spelling match, so an
    alternative transliteration still breaks down the canonical word in Hebrew.
    A HYPHENATED compound (mother-father, triple-son) is broken into its parts:
    each part is studied on its own, and a combined record joins them with a maqaf."""
    if name and "-" in name.strip("-"):
        raw_parts = [p for p in re.split(r"\s*-\s*", name.strip()) if p.strip()]
        if len(raw_parts) > 1:
            subs = [study(p) for p in raw_parts]
            subs = [s for s in subs if s]
            if subs:
                heb = "־".join(s["hebrew"] for s in subs)        # maqaf between parts
                letters, total = [], 0
                for s in subs:
                    letters += s.get("letters", [])
                    total += s.get("gematria", 0)
                meaning = "A hyphenated compound. " + "  +  ".join(
                    "%s (%s): %s" % (s["name"], s.get("translit", ""), (s.get("meaning", "") or "").rstrip("."))
                    for s in subs) + "."
                return {"name": name, "hebrew": heb,
                        "translit": "-".join(s.get("translit", "") for s in subs),
                        "meaning": meaning, "direct": False, "root": "",
                        "letters": letters, "gematria": total, "compound": True,
                        "parts": [{"name": s["name"], "hebrew": s["hebrew"],
                                   "translit": s.get("translit", ""), "meaning": s.get("meaning", ""),
                                   "gematria": s.get("gematria", 0)} for s in subs],
                        "note": "Each part is broken down above; the parts are joined here by a maqaf (־)."}
    if _has_arabic(name):          # an Arabic word (e.g. from the Qur'an): romanize -> Hebrew letters
        rom = ar_romanize(name).strip()
        heb = transliterate(re.sub(r"[^a-z]", "", rom.lower()))
        if heb:
            letters, total = dissect(heb)
            return {"name": name, "hebrew": heb, "translit": rom, "direct": False, "root": "",
                    "meaning": "An Arabic word (“%s”, romanized “%s”), written here in "
                               "Hebrew letters by sound." % (name, rom),
                    "note": "A cross-script transliteration — the Hebrew letters carry the Arabic "
                            "word's sound; its senses are looked up separately, not claimed from the letters.",
                    "letters": letters, "gematria": total}
    if _has_hebrew(name):          # a real Hebrew word (e.g. straight from the Torah): dissect it directly
        base = "".join(_HEB_FINALS.get(c, c) for c in name if ("א" <= c <= "ת") or c in _HEB_FINALS)
        if base:
            letters, total = dissect(base)
            rom = "".join(_HEB_ROM.get(c, "") for c in base)
            return {"name": name, "hebrew": base, "translit": rom, "direct": True, "root": "",
                    "meaning": "A Hebrew word, read right-to-left; its letters are broken down below "
                               "and its gematria summed.",
                    "note": "The letters are dissected directly from the Hebrew spelling; the word's "
                            "senses are looked up separately, not claimed from the letters.",
                    "letters": letters, "gematria": total}
    nn = _alias(_norm(name))
    e = _load().get(nn)
    if not e:
        vk = _variant_key(nn)
        alt = (_VARIDX or {}).get(vk) if vk else None
        if alt and alt != nn:
            e = _NAMES.get(alt)
    if not e:                                    # ordinary word -> the Hebrew the KJV renders it from
        rev = _strongs_rev().get(nn)
        if rev:
            heb, tr, key, kjv = rev
            e = {"hebrew": heb, "translit": tr,
                 "meaning": "The Hebrew word the King James text renders as “%s” "
                            "(Strong's %s: %s)." % (name, key, kjv.strip().rstrip(".")[:130]),
                 "note": "Not a name — the Hebrew that the KJV translates into this English word.",
                 "direct": True}
    if not e:                                    # last resort: phonetically write it in Hebrew
        heb = transliterate(nn)
        if heb:
            e = {"hebrew": heb, "translit": name,
                 "meaning": "No lexical Hebrew equivalent is recorded for this word, so its sound "
                            "is written here in Hebrew consonant-letters.",
                 "note": "A phonetic Hebrew transliteration — the letters carry the sound of the "
                         "word, not a Hebrew meaning.", "direct": False}
    if not e:
        return None
    heb = e.get("hebrew", "")
    letters, total = dissect(heb)
    default_note = ("A genuine Hebrew/Aramaic name." if e.get("direct")
                    else "Not a native Hebrew word — a phonetic Hebrew transliteration of the "
                         "name's most-likely spelling, with its sense reconstructed.")
    return {"name": name, "hebrew": heb, "translit": e.get("translit", ""),
            "meaning": e.get("meaning", ""), "direct": bool(e.get("direct", False)),
            "root": e.get("root", ""), "letters": letters, "gematria": total,
            "note": e.get("note") or default_note}


def has(name):
    return _norm(name) in _load()


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("names loaded:", len(_load()))
    for n in ["Adam", "Sabaoth", "Harmozel", "Barbelo", "Yaldabaoth"]:
        s = study(n)
        if s:
            print("\n%s  %s  [%s]  gematria=%d" % (n, s["hebrew"], s["translit"], s["gematria"]))
            print("  ", s["meaning"])
            for L in s["letters"]:
                print("    %s %-12s %d  %s" % (L["glyph"], L["name"], L["value"], L["meaning"][:40]))
