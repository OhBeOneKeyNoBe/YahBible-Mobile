"""Aramaic (Syriac) letter-by-letter dissection + transliteration -- the Aramaic parallel of
taviel_hebrew, so every word study carries Hebrew + Greek + Aramaic.

Aramaic square script IS the Hebrew square script (they are the same 22 consonants), so to
give the reader a visually DISTINCT third column we write Aramaic in the SYRIAC script -- the
living script of the Peshitta and the Aramaic-speaking church. Given any English word we write
its sound in Syriac letters (per the always-create rule: EVERY word gets a study), dissect it
letter-by-letter with the ancient Semitic pictographic meaning + the abjad numeric value, and
give the gematria (abjad) total. A genuine Syriac/Aramaic/Hebrew string is dissected directly.
"""

import re

# Syriac letter -> (name, translit, value, meaning). Values are the Syriac abjad (parallels
# the Hebrew/Greek numeral systems). Meanings are the shared ancient Semitic pictographs.
SYRIAC = {
    "ܐ": ("Alaph", "'", 1, "ox / strength, leader; the silent breath, the One."),
    "ܒ": ("Beth", "b", 2, "house / household, in, within."),
    "ܓ": ("Gamal", "g", 3, "camel / to lift up, to recompense, to deal out."),
    "ܕ": ("Dalath", "d", 4, "door / pathway, to enter, to move."),
    "ܗ": ("He", "h", 5, "window, lattice / behold, to reveal, breath."),
    "ܘ": ("Waw", "w", 6, "nail, hook / to fasten, to bind, 'and'."),
    "ܙ": ("Zain", "z", 7, "weapon, mattock / to cut, to nourish, to arm."),
    "ܚ": ("Heth", "kh", 8, "fence, wall / to separate, to protect, private."),
    "ܛ": ("Teth", "t", 9, "basket, coil / to surround, to store, good."),
    "ܝ": ("Yodh", "y", 10, "hand, arm / deed, work, to make, to worship."),
    "ܟ": ("Kaph", "k", 20, "open palm / to cover, to allow, to bend, to tame."),
    "ܠ": ("Lamadh", "l", 30, "ox-goad, staff / to teach, to urge, to lead, control."),
    "ܡ": ("Mim", "m", 40, "water / chaos, mighty, mass; the peoples."),
    "ܢ": ("Nun", "n", 50, "fish, seed / life, activity, continuity, the heir."),
    "ܣ": ("Semkath", "s", 60, "prop, support / to uphold, to lean upon, to trust."),
    "ܥ": ("'E", "'", 70, "eye, spring / to see, to know, to experience."),
    "ܦ": ("Pe", "p", 80, "mouth / to speak, to blow, word, edge."),
    "ܨ": ("Sadhe", "ts", 90, "fish-hook, side / to catch, to desire, to hunt, need."),
    "ܩ": ("Qoph", "q", 100, "back of the head, eye of a needle / to encircle, the least, time."),
    "ܪ": ("Resh", "r", 200, "head / chief, beginning, the highest, a person."),
    "ܫ": ("Shin", "sh", 300, "tooth / to consume, to destroy, to press, sharp; the Almighty."),
    "ܬ": ("Taw", "t", 400, "mark, cross / a sign, a covenant, to seal, the end."),
}

# accept the equivalent HEBREW-square letters as input (Aramaic square == Hebrew) -> the Syriac letter
_HEB_TO_SYR = {
    "א": "ܐ", "ב": "ܒ", "ג": "ܓ", "ד": "ܕ",
    "ה": "ܗ", "ו": "ܘ", "ז": "ܙ", "ח": "ܚ",
    "ט": "ܛ", "י": "ܝ", "כ": "ܟ", "ך": "ܟ",
    "ל": "ܠ", "מ": "ܡ", "ם": "ܡ", "נ": "ܢ",
    "ן": "ܢ", "ס": "ܣ", "ע": "ܥ", "פ": "ܦ",
    "ף": "ܦ", "צ": "ܨ", "ץ": "ܨ", "ק": "ܩ",
    "ר": "ܪ", "ש": "ܫ", "ת": "ܬ",
}

# English sound -> Syriac letters (mirrors the Hebrew transliterator)
_TL_DIGRAPHS = [("tsch", "ܛܫ"), ("sch", "ܫ"), ("tch", "ܛܫ"),
                ("sh", "ܫ"), ("ch", "ܚ"), ("ts", "ܨ"), ("tz", "ܨ"),
                ("th", "ܬ"), ("ph", "ܦ"), ("kh", "ܟ"), ("ck", "ܩ"),
                ("qu", "ܩܘ"), ("wh", "ܘ")]
_TL_SINGLE = {"a": "", "b": "ܒ", "c": "ܩ", "d": "ܕ", "e": "", "f": "ܦ",
              "g": "ܓ", "h": "ܗ", "i": "ܝ", "j": "ܝ", "k": "ܟ",
              "l": "ܠ", "m": "ܡ", "n": "ܢ", "o": "ܘ", "p": "ܦ",
              "q": "ܩ", "r": "ܪ", "s": "ܣ", "t": "ܬ", "u": "ܘ",
              "v": "ܘ", "w": "ܘ", "x": "ܩܣ", "y": "ܝ", "z": "ܙ"}
_VOWEL = {"a": "ܐ", "e": "ܐ", "i": "ܝ", "o": "ܘ", "u": "ܘ", "y": "ܝ"}


def _has_syriac(s):
    return any("܀" <= c <= "ݏ" for c in (s or ""))


def _has_hebrew(s):
    return any(c in _HEB_TO_SYR for c in (s or ""))


def transliterate(word):
    """Write ANY word's sound in Syriac consonant-letters, so every word gets a letter-study
    even when no lexical Aramaic equivalent exists (never returns empty)."""
    w = re.sub(r"[^a-z]", "", (word or "").lower())
    out, i = [], 0
    while i < len(w):
        hit = None
        for dg, syr in _TL_DIGRAPHS:
            if w.startswith(dg, i):
                hit = (syr, len(dg)); break
        if hit:
            out.append(hit[0]); i += hit[1]
        else:
            out.append(_TL_SINGLE.get(w[i], "")); i += 1
    syr = "".join(out)
    if not syr:                       # all-vowel words -> carry the vowels so it is never empty
        syr = "".join(_VOWEL.get(ch, "") for ch in w) or "ܐ"
    return syr


def _to_syriac(word):
    """Map a Hebrew-square Aramaic string to Syriac letters (keep Syriac as-is)."""
    return "".join(_HEB_TO_SYR.get(c, c) for c in (word or ""))


def dissect(word):
    """Letter-by-letter dissection of a Syriac string + the abjad (gematria) total."""
    letters, total = [], 0
    for ch in (word or ""):
        if ch in SYRIAC:
            name, tr, val, meaning = SYRIAC[ch]
            letters.append({"glyph": ch, "name": name, "translit": tr,
                            "meaning": meaning, "value": val})
            total += val
    return letters, total


def _romanize(word):
    return "".join(SYRIAC[c][1] for c in (word or "") if c in SYRIAC)


def study(name):
    """Given an English word (or a raw Aramaic/Syriac/Hebrew-square string), return its Syriac
    form, transliteration, letter-by-letter dissection, and abjad total. Never returns None for
    a real word -- every word gets an Aramaic study (mirrors taviel_hebrew.study)."""
    if not name:
        return {"found": False}
    raw = name.strip()
    if _has_syriac(raw) or _has_hebrew(raw):
        syr = _to_syriac(raw)
        letters, total = dissect(syr)
        return {"name": name, "aramaic": syr, "translit": _romanize(syr),
                "letters": letters, "gematria": total, "direct": True,
                "note": "A genuine Aramaic word, written in the Syriac script of the Peshitta."}
    syr = transliterate(raw)
    letters, total = dissect(syr)
    return {"name": name, "aramaic": syr, "translit": raw.lower(),
            "letters": letters, "gematria": total, "direct": False,
            "note": "A phonetic Aramaic transliteration -- the Syriac letters carry the sound "
                    "of the word, letter by letter, with the ancient Semitic meaning of each."}


if __name__ == "__main__":
    import sys
    for n in (sys.argv[1:] or ["light", "love", "the", "a", "Yeshua"]):
        s = study(n)
        print("%-10s %s  [%s]  gematria=%d" % (n, s["aramaic"], s["translit"], s["gematria"]))
